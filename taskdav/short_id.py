#!/usr/bin/env python

"""Given a complete set of IDs, reduces each one to the minimal initial string needed to distinguish it from the others"""

# TODO: think through API

class prefix_dict(dict):
   """A set that enables lookup based on the shortest unique prefix, for a relatively small number of string keys"""
   def search(self, prefix):
       """looks up all keys beginning with the given prefix"""
       return [key for key in self.iterkeys() if isinstance(key, basestring) and key.startswith(prefix)]

   def unique(self, prefix):
       """obtains the unique item starting with the given prefix - errors if search returns 0, 2 or more"""
       keys = self.search(prefix)
       if len(keys) > 1:
           raise ValueError("Could not distinguish between keys from %s: %s" % (prefix, ", ".join(keys)))
       elif not keys:
           raise KeyError("Could not find key starting with prefix %s" % prefix)
       return self[keys[0]]

   def shortest(self, key):
       """Obtains the shortest prefix for the given key that will match only that key out of the current set"""
       i = 1
       keys = self.search(key[:i])
       while i < len(key):
           if len(keys) == 1:
               break
           i += 1
           prefix = key[:i]
           keys = [k for k in keys if k.startswith(prefix)]
       return key[:i]

