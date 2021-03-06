
import collections
import os, os.path
import re

from . import debug, info, warning, error, fatal
from .Taxon import *

__version__ = 'parser 0.4'

"""

Not optional:

You must input a ruleset through parser.setup()
"""

def define_tags(lines, direction=-1, init='''import string\nprint("# yee-haw!")''', **kwargs):
	"""This is the major setup function for the module."""
	# customize here:
	highest_pri = len(lines)
	w = direction << highest_pri
	#
	my_globals = { 'Taxonomy': Taxonomy, 'tag': tag }
	exec(init, my_globals)
	for line_no, line in enumerate(lines):
		if not line.strip():
			continue
		for tokens in line.split(';'):
			params = dict(kwargs) # copy
			params['line'] = line_no
			# customize here:
			params['rank'] = w
			params['pri'] = line_no if (0 <= direction) else highest_pri-line_no
			#
			for token in tokens.split():
				if '=' in token:
					exec(token, my_globals, params)
				else:
					if '_' in token:
						# synonyms lookup to the token
						t = tag(token, synonyms=[token.replace('_', ' ')])
					else:
						t = tag(token)
					t.update(params)
		# customize here:
		w >>= 1
		#
#
def pack(list_of_tags):
	"""Given a list of strings and TaxonObjects, remove TaxonObjects with the same rank as the right-most TaxonObject (in-place). This also applies to duplicates.
	"""
	# get rightmost ranked object
	for i in range(-1, -len(list_of_tags), -1):
		if hasattr(list_of_tags[i], 'rank'):
			break
	else: # never broke during loop
		return list_of_tags
	r = list_of_tags[i].rank
	for t in list_of_tags[:i]:
		if hasattr(t, 'rank'):
			if (r == t.rank):
				list_of_tags.remove(t)
				debug("{t} removed from {list_of_tags}".format(**locals() ))
	return list_of_tags
def combine(*args):
	lists_of_tags = list(args)
	initial = lists_of_tags.pop(0)
	tags, nontags = split(initial)
	for superior in lists_of_tags:
		if not superior:
			continue
		assert isinstance(superior, (tuple, list))
		new_tags, new_nontags = split(superior)
		nontags.extend(new_nontags)
		for item in new_tags:
			if item:
				tags = pack(tags+[item])
	return tags, nontags
#
def convert(iterable, remove_tags=None, prepend_tags=None, append_tags=None):
	"""
>>> convert('red green blue banana APPLE nogreen purple red'.split())
['banana', 'APPLE', <purple>, <red>]

"""
	items = []
	my_removes = remove_tags[:] if remove_tags else []
	my_prepends = prepend_tags[:] if prepend_tags else []
	my_appends = append_tags[:] if append_tags else []
	### TODO: this is likely inefficient ###
	def extend(list_of_tags, item):
		"""Relies heavily on members added during runtime.
		"""
		if isinstance(item, TaxonObject):
			if hasattr(item, 'purge'):
				if item.purge:
					return list_of_tags
			if hasattr(item, 'removes'):
				my_removes.extend(item.removes)
			#if hasattr(item, 'fallback'): # TODO: causes weird error at items.append(item)
			#	items = item.fallback+items
			if hasattr(item, 'prepends'):
				for p in item.prepends:
					items.append(p)
					list_of_tags = pack(list_of_tags)
			if my_prepends:
				for p in my_prepends:
					items.append(p)
					list_of_tags = pack(list_of_tags)
			items.append(item)
			list_of_tags = pack(list_of_tags)
			if hasattr(item, 'appends'):
				for a in item.appends:
					items.append(a)
					list_of_tags = pack(list_of_tags)
			if my_appends:
				for a in my_appends:
					items.append(a)
					list_of_tags = pack(list_of_tags)
		elif (item in Taxonomy):
			extend(list_of_tags, tag(item))
		else:
			items.append(item)
		return pack(list_of_tags)
	for field, literal in enumerate(iterable):
		if not isinstance(literal, (str, TaxonObject)):
			raise ValueError(literal)
		if literal in Taxonomy or isinstance(literal, TaxonObject):
			extend(items, literal)
			#if literal == tag(None):
			#	items = []
			#else:
			#	extend(items, literal)
			continue
		else:
			token = name_cleaner(literal)
			if token.startswith('no'):
				n = token[2:]
				if n in Taxonomy:
					t = tag(n)
					my_removes.append(t)
				else:
					extend(items, token)
				continue
			elif token in Taxonomy:
				extend(items, token)
			else:
				extend(items, literal)
	if my_removes:
		info("Tags {} want to remove {}".format(items, my_removes))
		for n in set(items) & set(my_removes):
			items.remove(n)
	return pack(items)
def split(iterable, **kwargs):
	def key(t):
		try:
			return t.rank
		except:
			warning("{} unsortable".format(t))
			return 0
	cts = convert(iterable, **kwargs)
	tags, nontags = [], []
	for item in cts:
		if item:
			(tags if isinstance(item, TaxonObject) else nontags).append(item)
			tags.sort(key=key)
	debug("{} => {}+{}".format(iterable, tags, nontags))
#	if tags:
#		debug("pri={}, rank={}".format(max(t.pri for t in tags),
#									   sum(t.rank for t in tags)) )
	return tags, nontags
def arrange(iterable, **kwargs):
	"""
	>>> arrange('green blue +18 nogreen puce'.split()) 
	(10, -9, [<blue>, <puce>, '+18'])

	>>> arrange('green blue +18 nogreen mauve'.split()) 
	(10, -27, [<blue>, <purple>, <puce>, <mauve>, '+18'])

	"""
	tags, nontags = split(iterable, **kwargs)
	if tags:
		highest_pri = max(t.pri for t in tags)
		total_rank = sum(t.rank for t in tags)
	else:
		highest_pri = total_rank = 0
	return highest_pri, total_rank, tags+nontags
def _read(*args, delim=re.compile('\n\s*\n')):
	for fn in sorted(args):
		assert os.path.isfile(fn)
		if not os.path.getsize(fn):
			continue
		debug("Reading "+fn)
		with open(fn) as fi:
			yield from delim.split(fi.read())
def setup(arg, **kwargs):
	"""
Example:
parser.setup( glob.glob(os.path.expanduser('/path/to/rules')) )
	"""
	if not arg:
		Taxonomy = {None: {'id': 0, 'name': None }}
		return
	elif isinstance(arg, str): # single filename
		return setup([arg], **kwargs)
	elif isinstance(arg, (list, tuple)): # list of filenames
		define_tags(list(_read(*arg)), **kwargs)
	else:
		raise NotImplemented
	return arg
def get_custom_attributes():
	c = collections.Counter()
	for name, attribs in Taxonomy.items():
		c.update(attribs.keys())
	return c.most_common()


def print_Taxonomy(labels=[],
				   header="lno "+"rank".rjust(25)+" -pri- count label"):
	show_tags = set(labels)
	def key(args):
		"""Deals in the elements of Taxonomy.items()
		"""
		name, members = args
		if 'pri' in members:
			return -members['pri'], members['rank'], name or ''
		if 'rank' in members:
			return 0, members['rank'], name or ''
		else:
			return 0, 0, name or ''
		#return 'isolate' in members, members.get('pri', 0), -members.get('rank', 0), name
	#
	if header:
		print(header)
		print("="*len(header))
	#
	for n, (name, attribs) in \
		enumerate(sorted(Taxonomy.items(), key=key)):
		if name is None:
			debug("Ignoring tag 'None'")
			continue
		if show_tags:
			if name in show_tags:
				show_tags -= set([name])
			else:
				continue
		try:
			r = attribs['rank']
			p = attribs['pri']
			nbr_count = sum(1 for t, a in Taxonomy.items() if a.get('rank',None) == r)
			print("{:03d} {:25d} {:5.1f} {:5d} {}".format(n, r, p, nbr_count, tag(name) ))
		except KeyError as e:
			warning("{} unsortable: {}".format(name, e))
	print()
	if show_tags:
		for t in show_tags:
			print("Not found: {}".format(t))
		print()
	for attrib, count in get_custom_attributes():
		print(attrib, count)


if __name__ == '__main__':
	import doctest
	from glob import glob

	setup(sorted(glob('rules/*')))
	print_Taxonomy()
	doctest.testmod()
