#!/usr/bin/env python3
import os, os.path
from os.path import exists, isfile, isdir
import shutil

import parser, TagFile

class Namespace(dict):
	def __init__(self, *args, **kwargs):
		super(Namespace, self).__init__(*args, **kwargs)
		self.__dict__ = self

debug=print


def path_split(path, stopwords=['rules', 'sortme'], sep=os.path.sep, **kwargs):
	path_parts = [ p for p in path.split(sep) if p not in ['', '.', '..'] ]
	parts = []
	a = parts.append
	for p in path_parts:
		if ',' in p:
			sub_parts = p.split(',')
			tags, nontags = parser.split(sub_parts)
			if nontags:
				a(p)
			else:
				parts.extend(sub_parts)
		else:
			a(p)
	#if any(w in parts for w in stopwords):
	if set(stopwords) & set(parts):
		return [], path
	tags, s = parser.split(parts, **kwargs)
	return tags, sep.join(str(p) for p in s)
def path_arrange(*args, **kwargs):
	sep = kwargs.get('sep', os.path.sep)
	tags, newpath = path_split(*args, **kwargs)
	if tags:
		highest_pri = max(t.pri for t in tags)
		total_rank = sum(t.rank for t in tags)
	else:
		highest_pri = total_rank = 0
	return highest_pri, total_rank, sep.join(str(t) for t in tags+[newpath])
def path_detag(arg, tagfile='.tags', move=shutil.move, dest='tagged', **kwargs):
	tags, newpath = path_split(arg, **kwargs)
	if tags:
		my_dest = os.path.join(dest, newpath)
	else:
		debug('Moving {} to {}'.format(arg, dest))
		debug('Not entering {} into a tagfile'.format(arg))
		return newpath, None
	if newpath in ['.', '..', '']:
		tf = TagFile.TagFile(os.path.join(dest, tagfile))
	else:
		tf = TagFile.TagFile(os.path.join(my_dest, tagfile))
	if not isdir(my_dest):
		os.makedirs(my_dest)
	debug('Moving {} to {}'.format(arg, my_dest))
	tf.merge(newpath, tags)
	return newpath, tagfile
def walk(*args, **kwargs):
	for root, dirs, files in os.walk(*args):
		src = os.path.relpath(root)
		if (not files) or (src in ['.', '..', '']):
			debug("Skipping "+src)
			continue
		pri, rank, newpath = path_arrange(src, **kwargs)
		if src == os.path.relpath(newpath):
			debug("Doing nothing: "+src)
			continue
		file_size = sum(os.path.getsize(os.path.join(src, f)) for f in files)
		yield pri, rank, file_size, (src, newpath)
def chunk(*args, volumesize=0, **kwargs):
	def key(arg):
		p, r, s, _ = arg
		return r, -s
	if not volumesize:
		my_list = sorted(walk(*args, **kwargs), key=key)
		my_size = sum(s for p, r, s, _ in my_list)
		yield (0, (pairs for p, r, s, pairs in my_list))
	else:
		this_size, this_vol = 0, []
		for p, r, s, (src, dest) in sorted(walk(*args, **kwargs), key=key):
			assert s < volumesize
			if volumesize < this_size+s:
				yield this_size, this_vol
				this_size, this_vol = s, [ (src, dest) ]
			else:
				this_size += s
				this_vol.append( (src, dest) )
		if this_size:
			yield this_size, this_vol
#
if __name__ == '__main__':
	from glob import glob
	import sys

	parser.setup(glob('rules/*.rules'))
	for arg in sys.argv[1:]:
		print(arg, path_split(arg))
