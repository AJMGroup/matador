#!/usr/bin/python
# coding: utf-8
from scrapers import castep_scrapers
from export import doc2res
from print_utils import print_notify, print_success, print_failure
from sys import argv

fnames = argv[1:]
for fname in fnames:
    print_notify('Reading ' + fname)
    castep_dict, success = castep_scrapers.castep2dict(fname, db=False)
    if success:
        doc2res(castep_dict, fname.replace('.castep', ''), info=True, hash_dupe=True)
        print_success('Wrote .res file to ' + fname.replace('.castep', '') + '.res')
    else:
        print_failure('Unable to find final structure in ' + fname + '.')
print_success('Completed!')
