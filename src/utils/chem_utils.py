# coding: utf-8
""" This file defines some useful chemistry. """
import periodictable
import numpy as np
from utils.cursor_utils import get_array_from_cursor

FARADAY_CONSTANT_Cpermol = 96.485332e3
Cperg_to_mAhperg = 2.778e-1


def get_periodic_table():
    """ Return some periodic table macros. """
    periodic_table = dict()
    periodic_table['I'] = ['Li', 'Na', 'K', 'Rb', 'Cs', 'Fr']
    periodic_table['II'] = ['Be', 'Mg', 'Ca', 'Sr', 'Ba', 'Ra']
    periodic_table['III'] = ['B', 'Al', 'Ga', 'In', 'Tl']
    periodic_table['IV'] = ['C', 'Si', 'Ge', 'Sn', 'Pb']
    periodic_table['V'] = ['N', 'P', 'As', 'Sb', 'Bi']
    periodic_table['VI'] = ['O', 'S', 'Se', 'Te', 'Po']
    periodic_table['VII'] = ['F', 'Cl', 'Br', 'I', 'At']
    periodic_table['Tran'] = ['Sc', 'Ti', 'V', 'Cr', 'Mn', 'Fe', 'Co', 'Ni', 'Cu', 'Zn',
                              'Y', 'Zr', 'Nb', 'Mo', 'Tc', 'Ru', 'Rh', 'Pd', 'Ag', 'Cd',
                              'Hf', 'Ta', 'W', 'Re', 'Os', 'Ir', 'Pt', 'Au', 'Hg']
    periodic_table['Lan'] = ['La', 'Ce', 'Pr', 'Nd', 'Pm', 'Sm', 'Eu', 'Gd', 'Tb',
                             'Dy', 'Ho', 'Er', 'Tm', 'Yb', 'Lu']
    periodic_table['Act'] = ['Ac', 'Th', 'Pa', 'U', 'Np', 'Pu', 'Am', 'Cm', 'Bk',
                             'Cf', 'Es', 'Fm', 'Md', 'No', 'Lr']
    periodic_table['X'] = [elem for group in periodic_table.keys() for elem in periodic_table[group]]
    return periodic_table

def get_molar_mass(elem):
    """ Returns molar mass of chosen element. """
    return periodictable.elements.symbol(elem).mass

def get_atomic_number(elem):
    """ Returns atomic number of chosen element. """
    return periodictable.elements.symbol(elem).number

def get_num_intercalated(cursor):
    """ Return array of the number of intercalated atoms
    per host atom from a list of structures. """
    x = np.zeros((len(cursor)))
    comps = get_array_from_cursor(cursor, 'concentration')
    for idx, comp in enumerate(comps):
        if 1-comp == 0:
            x[idx] = np.NaN
        else:
            x[idx] = comp/(1-comp)
    return x

def get_capacities(x, m_B):
    """ Returns capacity in mAh/g from x in A_x B
    and m_B in a.m.u.
    """
    x = np.array(x)
    Q = x * FARADAY_CONSTANT_Cpermol * Cperg_to_mAhperg / m_B
    return Q

def get_atoms_per_fu(doc):
    """ Calculate the number of atoms per formula unit. """
    atoms_per_fu = 0
    for j in range(len(doc['stoichiometry'])):
        atoms_per_fu += doc['stoichiometry'][j][1]
    return atoms_per_fu

def get_formation_energy(chempots, doc):
    """ From given chemical potentials, calculate the simplest
    formation energy per atom of the desired document.
    """
    formation = doc['enthalpy_per_atom']
    for mu in chempots:
        for j in range(len(doc['stoichiometry'])):
            if mu['stoichiometry'][0][0] == doc['stoichiometry'][j][0]:
                formation -= (mu['enthalpy_per_atom'] * doc['stoichiometry'][j][1] /
                              get_atoms_per_fu(doc))
    return formation