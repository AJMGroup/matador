#!/usr/bin/python
# coding :utf-8
""" Run many CASTEP calculations from multiple res,
a single cell and a single param file.

Jobs in progress are listed in jobs.txt, failed
jobs are moved to bad_castep, completed jobs are
moved to completed and listed in finished_cleanly.txt.

Based on run.pl, run2.pl and PyAIRSS class CastepRunner.

Matthew Evans 2016
"""

from __future__ import print_function
from os import walk, makedirs, remove, sys
from os.path import isfile, exists
from collections import defaultdict
from scrapers.castep_scrapers import cell2dict, param2dict
from scrapers.castep_scrapers import res2dict, castep2dict
from export import doc2cell, doc2param, doc2res
from traceback import print_exc
import bson.json_util as json
import argparse
import multiprocessing as mp
import subprocess as sp
import glob


class BatchRun:
    """ A class that implements the running of multiple CASTEP jobs from a series
    of .res files and single cell and param files.
    """
    def __init__(self, *args, **kwargs):
        """ Check directory has valid contents and prepare log files and directories if
        not already prepared, then begin running calculations.
        """
        # analyse parallel allocation
        self.args = kwargs
        self.debug = self.args.get('debug')
        self.all_cores = mp.cpu_count()
        if self.args.get('nprocesses') is not None:
            self.nprocesses = self.args['nprocesses']
        else:
            self.nprocesses = 1
        if self.args.get('ncores') is not None:
            self.ncores = self.args['ncores']
        else:
            self.ncores = self.all_cores / self.nprocesses
        if self.ncores*self.nprocesses > self.all_cores:
            print('Requested more cores (' + str(self.ncores*self.nprocesses) +
                  ') than available (' + str(self.all_cores) + ').')
            exit('Exiting...')
        # scan directory for files to run
        self.file_lists = defaultdict(list)
        for root, dirs, files in walk('.'):
            for file in files:
                if root == '.':
                    if file.endswith('.res'):
                        self.file_lists['res'].append(file)
                    elif file.endswith('.cell'):
                        self.file_lists['cell'].append(file)
                    elif file.endswith('.param'):
                        self.file_lists['param'].append(file)
        # check for correct multiplicity of file types
        valid = True
        if len(self.file_lists['cell']) != 1:
            valid = False
            print('run3 requires exactly 1 cell file in folder, found',
                  len(self.file_lists['cell']))
        if len(self.file_lists['param']) != 1:
            valid = False
            print('run3 requires exactly 1 param file in folder, found',
                  len(self.file_lists['param']))
        if len(self.file_lists['res']) < 1:
            valid = False
            print('run3 requires at least 1 res file in folder, found',
                  len(self.file_lists['res']))
        if not valid:
            exit('Exiting...')

        # read cell and param files into dicts
        cell_seed = self.file_lists['cell'][0]
        param_seed = self.file_lists['param'][0]
        self.cell_dict, cell_success = cell2dict(cell_seed)
        if not cell_success:
            print('Failed to parse cell file')
        self.param_dict, param_success = param2dict(param_seed, db=False)
        if not param_success:
            print('Failed to parse cell file')
        success = False
        if cell_success and param_success:
            success = True
        if not success:
            exit()
        # print(json.dumps(self.cell_dict, indent=2))
        # print(json.dumps(self.param_dict, indent=2))
        # delete source from cell and param
        del self.cell_dict['source']
        del self.param_dict['source']
        # prepare folders and text files
        self.paths = dict()
        self.paths['completed_dir'] = 'completed'
        self.paths['failed_dir'] = 'bad_castep'
        self.paths['jobs_fname'] = 'jobs.txt'
        self.paths['completed_fname'] = 'finished_cleanly.txt'
        if not isfile(self.paths['jobs_fname']):
            with open(self.paths['jobs_fname'], 'a'):
                pass
        if not isfile(self.paths['completed_fname']):
            with open(self.paths['completed_fname'], 'a'):
                pass
        pass

    def spawn(self):
        # begin running calculations that have not already started
        # initialise pool of processes
        procs = []
        for ind in range(self.nprocesses):
            procs.append(mp.Process(target=self.perform_new_calculations,
                         args=(self.file_lists['res'], self.paths)))
        for proc in procs:
            proc.start()

    def perform_new_calculations(self, res_list, paths):
        """ Perform all calculations that have not already
        failed or finished to completion. """
        for res in res_list:
            running = False
            with open(paths['jobs_fname'], 'r') as job_file:
                flines = job_file.readlines()
                for line in flines:
                    if res in line:
                        running = True
                        break
            if not running:
                with open(paths['jobs_fname'], 'a') as job_file:
                    job_file.write(res+'\n')
                # create full relaxer object for creation and running of job
                try:
                    print('Starting', res)
                    FullRelaxer(paths=self.paths,
                                ncores=self.ncores,
                                res=res,
                                param_dict=self.param_dict,
                                cell_dict=self.cell_dict,
                                debug=self.debug)
                    print('Completed', res)
                except:
                    print(res, 'failed')
                    pass
        return

class FullRelaxer:
    """ Turn res file name into "full relax" CASTEP job.
    """
    def __init__(self, paths, ncores, res, param_dict, cell_dict, debug):
        """ Make the files to run the calculation and handle
        the calling of CASTEP itself.
        """
        self.paths = paths
        self.ncores = ncores
        self.executable = 'castep'
        self.debug = debug
        # read in initial structure
        res_dict, success = res2dict(res)
        if not success:
            return False
        calc_doc = res_dict
        # set seed name
        self.seed = calc_doc['source'][0].replace('.res', '')
        # update global doc with cell and param dicts for folder
        calc_doc.update(cell_dict)
        calc_doc.update(param_dict)
        if self.debug:
            print(json.dumps(calc_doc, indent=2))
        self.success = self.relax(calc_doc)
        if not success:
            raise RuntimeError('Failed to relax structure')

    def relax(self, calc_doc):
        """ Set up the calculation to perform 4 sets of two steps,
        then continue with the remainder of steps.
        """
        seed = self.seed
        geom_max_iter_list = [2, 2, 2, 2, calc_doc['geom_max_iter']]
        for num_iter in geom_max_iter_list:
            calc_doc['geom_max_iter'] = num_iter
            print(calc_doc['geom_max_iter'])
            try:
                # delete any existing files
                if isfile(self.seed + '.param'):
                    print('IS FILE?')
                    remove(seed+'.param')
                if isfile(seed + '.cell'):
                    print('IS FILE?')
                    remove(seed+'.cell')
            except:
                print_exc()
                print('Failed to clean up...')
                raise RuntimeError('Failure')
            try:
                # write new param and cell
                doc2param(calc_doc, seed, hash_dupe=False)
                doc2cell(calc_doc, seed, hash_dupe=False, copy_pspots=False)
            except:
                print('Failed to prepare calc')
                sys('rm ' + seed + '.cell')
                sys('rm ' + seed + '.param')
                raise RuntimeError('Failure')
            try:
                # run CASTEP
                process = self.castep(seed)
                process.communicate()
                # scrape new structure from castep file
            except:
                print('Failed to start CASTEP...')
                print_exc()
                sys('rm ' + seed + '.cell')
                sys('rm ' + seed + '.param')
                raise RuntimeError('Failure')
            opti_dict, success = castep2dict(seed)
            if not success and opti_dict == '':
                print('Failed to scrape castep file...')
                return False
            if opti_dict['optimised'] == True:
                if not exists('completed'):
                    makedirs('completed')
                print('Successfully relaxed', seed)
                # write res and castep file out to completed folder
                doc2res(opti_dict, 'completed/' + seed)
                sys('mv ' + seed + '.castep' + ' completed/' + seed + '.castep')
                sys('mv ' + seed + '.param' + ' completed/' + seed + '.param')
                sys('mv ' + seed + '.cell' + ' completed/' + seed + '.cell')
                # clean up rest of files
                sys('rm ' + seed + '.*')
                return True
            else:
                err_file = seed + '*.err'
                for globbed in glob.glob(pspot_seed):
                    if isfile(globbed):
                        if not exists('bad_castep'):
                            makedirs('bad_castep')
                        print('CASTEP crashed... skipping...')
                        sys('mv ' + seed + '* bad_castep')
                        return False
                calc_doc.update(opti_dict)
                doc2res(calc_doc, seed + '-save')

    def castep(self, seed):
        """ Calls CASTEP on desired seed with desired number of cores. """
        if self.ncores == 1:
            process = sp.Popen(['nice', '-n', '15', self.executable, seed])
        else:
            process = sp.Popen(['nice', '-n', '15', 'mpirun', '-n',
                                str(self.ncores), self.executable, seed])
        return process


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        prog='run3',
        description='Run multiple CASTEP geometry optmizations from a series of .res \
                     files and single cell and param files. The calculation will be \
                     restarted after 3 geom_opt steps by default, or otherwise by \
                     value of geom_max_iter in the param file.',
        epilog='Written by Matthew Evans (2016), based primarily on run.pl and run2.pl \
                by Chris Pickard and Andrew Morris and PyAIRSS CastepRunner by Jamie Wynn.')
    parser.add_argument('-nc', '--ncores', type=int,
                        help='number of cores CASTEP per job [DEFAULT=cpu_count/nprocesses]')
    parser.add_argument('-np', '--nprocesses', type=int,
                        help='number of concurrent calculations [DEFAULT=1]')
    parser.add_argument('-d', '--debug', action='store_true',
                        help='debug output')
    args = parser.parse_args()
    runner = BatchRun(ncores=args.ncores, nprocesses=args.nprocesses, debug=args.debug)
    runner.spawn()
