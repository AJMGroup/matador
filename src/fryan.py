#!/usr/bin/python
# coding: utf-8
from __future__ import print_function
import pymongo as pm
import numpy as np
import argparse
import bson.json_util as json
import re

class DBQuery:
    ''' Class that implements queries to MongoDB
    structure database.
    '''

    def __init__(self, **kwargs):
        ''' Initialise the query with command line
        arguments.
        '''
        self.client = pm.MongoClient()
        self.repo = self.client.crystals.repo
        self.args = kwargs
        # self.args = args
        self.top = self.args.get('top') if self.args.get('top') != None else 10
        self.details = self.args.get('details')
        self.source = self.args.get('source')
        # benchmark enthalpy to display (set by calc_match)
        self.gs_enthalpy = 0.0
        if self.args.get('pressure') != None:
            cursor = self.repo.find(
                    {
                    'external_pressure': {'$in': [[self.args.get('pressure')]]}
                    }
                    )
            self.repo = self.temp_collection(cursor)
        if self.args.get('id') != None:
            cursor = self.repo.find({'text_id': self.args.get('id')})
            self.display_results(cursor, details=True)
            cursor = self.repo.find({'text_id': self.args.get('id')})
            if self.args.get('calc_match'):
                cursor = self.query_calc('cursor')
                if self.args.get('composition') != None or self.args.get('stoichiometry') != None:
                    self.repo = self.temp_collection(cursor)
        if self.args.get('stoichiometry') != None:
            cursor = self.query_stoichiometry()
        elif self.args.get('composition') != None:
            cursor = self.query_composition()
        else:
            cursor = self.repo.find().sort('enthalpy_per_atom', pm.ASCENDING)
        # drop any temporary collection
        try:
            self.temp.drop()
        except:
            pass
        if self.args.get('main'):
            if cursor.count() != 0:
                if cursor.count() > self.top:
                    self.display_results(cursor[:self.top], details=self.details)
                else:
                    self.display_results(cursor, details=self.details)
        else:
            self.cursor = cursor

    def display_results(self, cursor, details=False):
        ''' Print query results in a cryan-like fashion. '''
        struct_string = []
        detail_string = []
        source_string = []
        gs_enthalpy = 0
        header_string = "{:^24}".format('ID')
        header_string += "{:^12}".format('Pressure')
        header_string += "{:^12}".format('Volume/fu') 
        header_string += "{:^18}".format('Enthalpy/atom')
        header_string += "{:^12}".format('Space group')
        header_string += "{:^10}".format('Formula')
        header_string += "{:^8}".format('# fu')
        for ind, doc in enumerate(cursor):
            sub_string = ''
            atom_per_fu = 0
            for item in doc['stoichiometry']:
                for item_ind, subitem in enumerate(item):
                    if item_ind == 0:
                        atom_per_fu += 1
                    if subitem != 1:
                        sub_string += str(subitem)
            struct_string.append(
                    "{:^24}".format(doc['text_id'][0]+' '+doc['text_id'][1])
                    + "{:^ 12.3f}".format(doc['pressure'])
                    + "{:^12.3f}".format(atom_per_fu * doc['cell_volume'] / doc['num_atoms'])
                    + "{:^18.5f}".format(doc['enthalpy_per_atom'] - self.gs_enthalpy)
                    + "{:^12}".format(doc['space_group']))
            struct_string[-1] += "{:^10}".format(sub_string)
            struct_string[-1] += "{:^8}".format(doc['num_atoms']/atom_per_fu)
            if ind == 0 and self.gs_enthalpy == 0:
                self.gs_enthalpy = doc['enthalpy_per_atom']
            if details:
                detail_string.append(12 * ' ' + u"└───────────── ")
                if 'spin_polarized' in doc:
                    if doc['spin_polarized']:
                        detail_string[-1] += 'S'
                detail_string[-1] += doc['xc_functional']
                detail_string[-1] += ', ' + "{:4.2f}".format(doc['cut_off_energy']) + ' eV'
                try:
                    detail_string[-1] += ', ' + "{:4.2f}".format(doc['external_pressure'][0][0]) + ' GPa'
                except: 
                    pass
                try:
                    detail_string[-1] += ', ' + doc['kpoints_mp_spacing'] + ' 1/A'
                except:
                    pass
            if self.source:
                source_string.append('')
                for file in doc['source']:
                    source_string[-1] += 18*' ' + u"└───────────── "+ file[2:] + '\n'
        print(len(header_string)*'─')
        print(header_string)
        print(len(header_string)*'─')
        for ind, string in enumerate(struct_string):
            print(string)
            if details:
                print(detail_string[ind])
            if self.source:
                print(source_string[ind])
        
    def query_stoichiometry(self):
        ''' Query DB for particular stoichiometry. '''
        # alias stoichiometry
        stoich = self.args.get('stoichiometry')
        # if there's only one string, try split it by caps
        if len(stoich) == 1:
            stoich = [elem for elem in re.split(r'([A-Z][a-z]*)', stoich[0]) if elem]
        elements = []
        fraction = []
        for i in range(0, len(stoich), 1):
            if not bool(re.search(r'\d', stoich[i])):
                elements.append(stoich[i])
                try:
                    fraction.append(float(stoich[i+1]))
                except:
                    fraction.append(1.0)
        fraction = np.asarray(fraction)
        fraction /= np.min(fraction)
        # pyMongo doesn't like generators... could patch pyMongo?
        # cursor = self.repo.find({'stoichiometry.'+[element for element in elements]: {'$exists' : True}})
        if len(elements) == 1:
            cursor = self.repo.find({'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}})
        elif len(elements) == 2:
            cursor = self.repo.find({ '$and': [ 
                                        {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}}
                                    ]})
        elif len(elements) == 3:
            cursor = self.repo.find({ '$and': [ 
                                        {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}}
                                    ]})
        elif len(elements) == 4:
            cursor = self.repo.find({ '$and': [ 
                                        {'stoichiometry' : {'$in' : [[elements[0], fraction[0]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[1], fraction[1]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[2], fraction[2]]]}},
                                        {'stoichiometry' : {'$in' : [[elements[3], fraction[3]]]}}
                                    ]})
        cursor.sort('enthalpy_per_atom', pm.ASCENDING)
        print(cursor.count(), 'structures found with the desired stoichiometry.')
        
        return cursor
    
    def query_composition(self):
        ''' Query DB for all structures containing 
        all the elements taken as input.
        '''
        elements = self.args.get('composition')
        # if there's only one string, try split it by caps
        if len(elements) == 1:
            elements = [elem for elem in re.split(r'([A-Z][a-z]*)', elements[0]) if elem]
        try:
            for elem in elements:
                if bool(re.search(r'\d', elem)):
                    raise RuntimeError('Composition string cannot contain a number.')
        except Exception as oops:
            print(oops)
            return EmptyCursor()
        # pyMongo doesn't like generators... could patch pyMongo?
        # cursor = self.repo.find({'stoichiometry.'+[element for element in elements]: {'$exists' : True}})
        if len(elements) == 1:
            cursor = self.repo.find({'atom_types' : {'$in' : [elements[0]]}})
        elif len(elements) == 2:
            cursor = self.repo.find({ '$and': [ 
                                        {'atom_types' : {'$in' : [elements[0]]}},
                                        {'atom_types' : {'$in' : [elements[1]]}}
                                    ]})
        elif len(elements) == 3:
            cursor = self.repo.find({ '$and': [ 
                                        {'atom_types' : {'$in' : [elements[0]]}},
                                        {'atom_types' : {'$in' : [elements[1]]}},
                                        {'atom_types' : {'$in' : [elements[2]]}}
                                    ]})
        elif len(elements) == 4:
            cursor = self.repo.find({ '$and': [ 
                                        {'atom_types' : {'$in' : [elements[0]]}},
                                        {'atom_types' : {'$in' : [elements[1]]}},
                                        {'atom_types' : {'$in' : [elements[2]]}},
                                        {'atom_types' : {'$in' : [elements[3]]}}
                                    ]})
        cursor.sort('enthalpy_per_atom', pm.ASCENDING)
        print(cursor.count(), 'structures found with desired composition')

        return cursor

    def query_calc(self, cursor):
        ''' Find all structures with matching
        accuracy to specified structure. '''
        doc = cursor[0]
        self.gs_enthalpy = doc['enthalpy_per_atom']
        if cursor.count() != 1:
            return cursor
        else:
            cursor_match = self.repo.find({ '$and': [
                                        {'xc_functional' : doc['xc_functional']},
                                        {'cut_off_energy': doc['cut_off_energy']},
                                        {'external_pressure': doc['external_pressure']}
                                    ]})
            cursor_match.sort('enthalpy_per_atom', pm.ASCENDING)
            print(cursor_match.count(), 'structures found with parameters above.')
            return cursor_match

    def temp_collection(self, cursor):
        ''' Create temporary collection
        for successive filtering. 
        '''
        # check temp doesn't already exist; drop if it does
        try:
            self.client.crystals.temp.drop()
        except:
            pass
        self.temp = self.client.crystals.temp
        if cursor.count() != 0:
            self.temp.insert(cursor)
        else:
            self.temp.drop()
            exit('No structures found.')
        return self.temp

class EmptyCursor:
    ''' Empty cursor class for failures. '''
    def count(self):
        return 0 

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Query MongoDB structure database.',
            epilog='Written by Matthew Evans (2016). Based on the cryan concept by Chris Pickard.')
    group = parser.add_argument_group()
    group.add_argument('-s', '--stoichiometry', nargs='+', type=str,
        help='choose a stoichiometry, e.g. Ge 1 Te 1 Si 3, or GeTeSi3')
    group.add_argument('-c', '--composition', nargs='+', type=str,
        help='find all structures containing the given elements, e.g. GeTeSi.')
    group.add_argument('-i', '--id', type=str, nargs='+',
            help='specify a particular structure by its text_id')
    parser.add_argument('-t', '--top', type=int,
            help='number of structures to show (DEFAULT: 10)')
    parser.add_argument('-d', '--details', action='store_true',
            help='show as much detail about calculation as possible')
    parser.add_argument('-p', '--pressure', type=float,
            help='specify an isotropic external pressure to search for, e.g. 10 (GPa)')
    parser.add_argument('--source', action='store_true',
            help='print filenames from which structures were wrangled')
    parser.add_argument('-ac', '--calc-match', action='store_true',
            help='display calculations of the same accuracy as specified id')
    args = parser.parse_args()
    if args.calc_match and args.id == None:
        exit('--calc-match requires -i or --id')
    query = DBQuery(stoichiometry=args.stoichiometry,
                    composition=args.composition,
                    id=args.id,
                    top=args.top,
                    details=args.details,
                    pressure=args.pressure,
                    source=args.source,
                    match_calc=args.calc_match,
                    main=True)