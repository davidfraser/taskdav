#!/usr/bin/env python

import short_id
from helpers import *

def test_empty():
    edict = short_id.prefix_dict()
    assert len(edict) == 0
    assert not edict
    assert edict.keys() == []
    assert edict.search("") == []
    assert edict.search("0") == []
    assert raises(KeyError, edict.unique, "a")
    assert edict.shortest("bcd") == "bcd"

def test_simple():
    indict = short_id.prefix_dict()
    indict["test"] = "me"
    indict["teach"] = "you"
    assert len(indict) == 2
    assert indict
    assert sorted(indict.keys()) == ["teach", "test"]
    assert sorted(indict.search("")) == ["teach", "test"]
    assert sorted(indict.search("t")) == ["teach", "test"]
    assert sorted(indict.search("e")) == []
    assert raises(KeyError, indict.unique, "e")
    assert indict.unique("teach") == "you"
    assert indict.shortest("teach") == "tea"
    assert indict.shortest("pumpkin") == "pumpkin"


