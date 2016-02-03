// vi: set expandtab ts=4 sw=4:
#ifndef atomstruct_PBManager
#define atomstruct_PBManager

#include <map>
#include <string>

#include "imex.h"

// "forward declare" PyObject, which is a typedef of a struct,
// as per the python mailing list:
// http://mail.python.org/pipermail/python-dev/2003-August/037601.html
#ifndef PyObject_HEAD
struct _object;
typedef _object PyObject;
#endif
    
namespace atomstruct {

class AtomicStructure;
class ChangeTracker;
class CoordSet;
class Proxy_PBGroup;

class BaseManager {
public:
    // so that subclasses can create multiple types of groups...
    static const int GRP_NONE = 0;
    static const int GRP_NORMAL = GRP_NONE + 1;
    typedef std::map<std::string, Proxy_PBGroup*>  GroupMap;
    typedef std::map<AtomicStructure*, int>  SessionStructureToIDMap;
    typedef std::map<int, AtomicStructure*>  SessionIDToStructureMap;
protected:
    ChangeTracker*  _change_tracker;
    GroupMap  _groups;
    SessionStructureToIDMap*  _ses_struct_to_id_map;
    SessionIDToStructureMap*  _ses_id_to_struct_map;
public:
    BaseManager(ChangeTracker* ct): _change_tracker(ct) {}
    virtual  ~BaseManager();

    ChangeTracker*  change_tracker() { return _change_tracker; }
    virtual Proxy_PBGroup*  get_group(
            const std::string& name, int create = GRP_NONE) = 0;
    const GroupMap&  group_map() const { return _groups; }
    SessionStructureToIDMap*  ses_struct_to_id_map() const { return _ses_struct_to_id_map; }
    SessionIDToStructureMap*  ses_id_to_struct_map() const { return _ses_id_to_struct_map; }
    void  session_restore(int version, int** ints, float** floats, PyObject* misc);
    int  session_info(PyObject** ints, PyObject** floats, PyObject** misc) const;
};

class StructureManager: public BaseManager {
protected:
    AtomicStructure*  _structure;
public:
    StructureManager(AtomicStructure* structure);
    virtual  ~StructureManager() {}

    AtomicStructure*  structure() const { return _structure; }
};

// global pseudobond manager
// Though for C++ purposes it could use PBGroup instead of Proxy_PBGroup,
// using proxy groups allows them to be treated uniformly on the Python side
class PBManager: public BaseManager {
public:
    PBManager(ChangeTracker* ct): BaseManager(ct) {}

    void  delete_group(Proxy_PBGroup*);
    Proxy_PBGroup*  get_group(const std::string& name, int create = GRP_NONE);
};

class AS_PBManager: public StructureManager
{
public:
    static const int  GRP_PER_CS = GRP_NORMAL + 1;
private:
    friend class AtomicStructure;
    friend class CoordSet;
    AS_PBManager(AtomicStructure* as): StructureManager(as) {}

    void  remove_cs(const CoordSet* cs);
public:
    ChangeTracker*  change_tracker() const;
    void  delete_group(Proxy_PBGroup*);
    Proxy_PBGroup*  get_group(const std::string& name, int create = GRP_NONE);
};

}  // namespace atomstruct

#endif  // atomstruct_PBManager
