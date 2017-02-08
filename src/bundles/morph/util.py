PreferredAtoms = [
        "CA",
        "P",
        "N",
        "C",
        "O5'",
        "O3'",
]

def getAtomList(rList):
        """Construct a list of CA/P atoms from residue list (ignoring
        residues that do not have either atom)"""
        aList = []
        if len(rList) > 2:
                atomsPerResidue = 1
        elif len(rList) > 1:
                atomsPerResidue = 2
        else:
                atomsPerResidue = 3
        for r in rList:
                atoms = set()
                failed = False
                while len(atoms) < atomsPerResidue:
                        for aname in PreferredAtoms:
                                a = r.find_atom(aname)
                                if a is None or a in atoms:
                                        continue
                                atoms.add(a)
                                break
                        else:
                                for a in r.atoms:
                                        if a not in atoms:
                                                atoms.add(a)
                                                break
                                else:
                                        failed = True
                        if failed:
                                break
                aList.extend(atoms)
        #print "%d residues -> %d atoms" % (len(rList), len(aList))
        return aList
                        
def copyMolecule(m, copyXformCoords=False, copyPBG=True):
        """Copy molecule and return both copy and map of corresponding atoms"""
        c = m.copy()
        atomMap = {a:ca for a,ca in zip(m.atoms, c.atoms)}
        residueMap = {r:cr for r,cr in zip(m.residues, c.residues)}
        return c, atomMap, residueMap

def timestamp(s):
        import time
        print ("%s: %s" % (time.ctime(time.time()), s))
