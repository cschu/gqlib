import csv
import os
import time
import sys
from collections import Counter
from datetime import datetime
import contextlib

import numpy
import pandas

from gffquant.bamreader import BamFile
from gffquant.gff_dbm import GffDatabaseManager
from gffquant.overlap_counter import OverlapCounter

SUPPL_ALN_FLAG = 0x800
MATE_UNMAPPED_FLAG = 0x8
FIRST_IN_PAIR_FLAG = 0x40
SECOND_IN_PAIR_FLAG = 0x80
REVCOMP_ALIGNMENT = 0x10


DEBUG = True


class AmbiguousAlignmentRecordKeeper:
	def __init__(self, fn):
		self.annotated = set()
		self.unannotated = set()
		self.readids = dict()
		self.ambig_dump = open(fn, "at")
	def __enter__(self):
		return self
	def __exit__(self):
		self.ambig_dump.close()

class FeatureQuantifier:

	def __init__(self, gff_db, gff_index, out_prefix="gffquant", ambig_mode="unique_only"):
		self.gff_dbm = GffDatabaseManager(gff_db, gff_index)
		self.umap_cache = dict()
		self.overlap_counter = OverlapCounter(out_prefix)
		self.out_prefix = out_prefix
		self.ambig_mode = ambig_mode
		print("Ambig mode:", self.ambig_mode)

	def process_unique_cache(self, rid, ref):
		for qname, uniq_aln in self.umap_cache.items():
			n_aln = len(uniq_aln)
			if n_aln == 1:
				start, end, flag = uniq_aln[0][1:]
				rev_strand = flag & REVCOMP_ALIGNMENT
			elif n_aln == 2:
				start, end = BamFile.calculate_fragment_borders(*uniq_aln[0][1:-1], *uniq_aln[1][1:-1])
				rev_strand = None
			else:
				print("WARNING: more than two primary alignments for {qname} ({n}). Ignoring.".format(qname=qname, n=n_aln), file=sys.stderr, flush=True)
				continue

			self.overlap_counter.update_unique_counts(rid, self.gff_dbm.get_overlaps(ref, start, end), rev_strand=rev_strand)

		self.umap_cache.clear()

	def process_alignments(self, bam):
		t0 = time.time()
		current_ref, current_rid = None, None

		ambig_reads = AmbiguousAlignmentRecordKeeper() if self.ambig_mode == "1overN" else contextlib.nullcontext
			

		with open(self.out_prefix + ".ambig_tmp.txt", "wt") as ambig_out_tmp:
			annotated, unannotated = set(), set()
			qname_d = dict()
			for aln_count, aln in bam.get_alignments(allow_multiple=self.ambig_mode != "unique_only", allow_unique=True, disallowed_flags=SUPPL_ALN_FLAG):
				start, end = aln.start, aln.end
				qname = aln.qname

				if aln.rid != current_rid:
					if current_rid is not None:
						self.process_unique_cache(current_rid, current_ref)
					current_ref, current_rid = bam.get_reference(aln.rid)[0], aln.rid

					print("{time}\tNew reference: {ref} ({rid}/{n_ref}). {n_aln} alignments processed.".format(
						time=datetime.now().strftime("%m/%d/%Y,%H:%M:%S"),
						ref=current_ref, rid=aln.rid, n_ref=bam.n_references(), n_aln=aln_count),
						file=sys.stderr, flush=True)

				rev_strand = aln.flag & REVCOMP_ALIGNMENT
				if aln.is_ambiguous() and self.ambig_mode in ("dist1", "1overN"):
					overlaps = self.gff_dbm.get_overlaps(current_ref, start, end)
					if overlaps:
						qname_id = qname_d.setdefault(qname, len(qname_d))
						annotated.add(qname_id)
						for ovl in overlaps:
							print(qname_id, aln_count, aln.rid, ovl.begin, ovl.end, aln.flag, file=ambig_out_tmp, sep="\t")
					else:
						unannotated.add(qname_id)
				elif aln.is_unique() and aln.is_paired() and aln.rid == aln.rnext and not aln.flag & MATE_UNMAPPED_FLAG:
					# need to keep track of read pairs to avoid dual counts
					# check if the mate has already been seen
					#mates = self.umap_cache.setdefault(qname, list())
					#if mates:
					#	# if it has, calculate the total fragment size and remove the pair from the cache
					#	if aln.rnext != mates[0][0]:
					#		print("WARNING: alignment {qname} seems to be corrupted: {aln1} {aln2}".format(qname=qname, aln1=str(aln), aln2=str(mates[0])), flush=True, file=sys.stderr)
					#		continue # i don't think this ever happens
					#	else:
					#		start, end = BamFile.calculate_fragment_borders(aln.start, aln.end, *mates[0][1:-1])
					#		rev_strand = None
					#		del self.umap_cache[qname]
					#else:
					#	# otherwise cache the first encountered mate and advance to the next read
					#	mates.append((aln.rid, aln.start, aln.end, aln.flag))
					#	continue
					start, end, rev_strand = self._process_unique_properly_paired_alignment(self, aln)
					if start is None:
						continue

				# at this point only single-end reads and merged pairs should be processed here ( + ambiguous reads in "all1" mode )
				self.overlap_counter.update_unique_counts(aln.rid, self.gff_dbm.get_overlaps(current_ref, start, end), rev_strand=rev_strand)

		self.process_unique_cache(current_rid, current_ref)
		t1 = time.time()

		print("Processed {n_align} alignments in {n_seconds:.3f}s.".format(
		    n_align=aln_count, n_seconds=t1-t0), flush=True
		)

		return len(unannotated.difference(annotated))

	def _process_unique_properly_paired_alignment(self, aln):
		# need to keep track of read pairs to avoid dual counts
		# check if the mate has already been seen
		mates = self.umap_cache.setdefault(aln.qname, list())
		start, end, rev_strand = None, None, None #TODO this requires some extra magic for strand-specific paired-end RNAseq
		if mates:
			# if it has, calculate the total fragment size and remove the pair from the cache
			if aln.rnext != mates[0][0]:
				print("WARNING: alignment {qname} seems to be corrupted: {aln1} {aln2}".format(qname=aln.qname, aln1=str(aln), aln2=str(mates[0])), flush=True, file=sys.stderr)
				# continue # i don't think this ever happens
			else:
				start, end = BamFile.calculate_fragment_borders(aln.start, aln.end, *mates[0][1:-1])
				rev_strand = None
				del self.umap_cache[qname]
		else:
			# otherwise cache the first encountered mate and advance to the next read
			mates.append((aln.rid, aln.start, aln.end, aln.flag))

		return start, end, rev_strand
		


	def _read_ambiguous_alignments(self, ambig_in):
		ambig_aln = pandas.read_csv(ambig_in, sep="\t", header=None)
		return ambig_aln.sort_values(axis=0, by=0)

	def _process_ambiguous_aln_groups(self, ambig_aln, bam):
		n_align, current_group = 0, None
		for aln in ambig_aln.itertuples(index=False, name=None):
			if current_group is None or current_group.qname != aln[0]:
				if current_group:
					n_align += current_group.n_align()
					current_group.resolve(self.overlap_counter, self.gff_dbm, bam, distmode=self.ambig_mode)
				current_group = AmbiguousAlignmentGroup(aln)
			else:
				current_group.add_alignment(aln)

		if current_group is not None:
			n_align += current_group.n_align()
			current_group.resolve(self.overlap_counter, self.gff_dbm, bam, distmode=self.ambig_mode)

		return n_align

	def process_data(self, bamfile, strand_specific=False):
		bam = BamFile(bamfile)
		unannotated = self.process_alignments(bam)

		print(self.gff_dbm._read_data.cache_info(), flush=True)
		self.gff_dbm._read_data.cache_clear()
		print(self.gff_dbm._get_tree.cache_info(), flush=True)
		self.gff_dbm._get_tree.cache_clear()

		if self.ambig_mode in ("dist1", "1overN"):
			t0 = time.time()

			ambig_aln_file = self.out_prefix + ".ambig_tmp.txt"
			ambig_aln = self._read_ambiguous_alignments(ambig_aln_file)
			n_align = self._process_ambiguous_aln_groups(ambig_aln, bam)

			if not DEBUG:
				os.remove(self.out_prefix + ".ambig_tmp.txt")

			t1 = time.time()
			print("Processed {n_align} secondary alignments in {n_seconds:.3f}s.".format(
				n_align=n_align, n_seconds=t1-t0), flush=True)

		self.overlap_counter.annotate_counts(bam, self.gff_dbm, strand_specific=strand_specific)
		self.overlap_counter.unannotated_reads += unannotated
		self.overlap_counter.dump_counts(bam, strand_specific=strand_specific)

		print("Finished.", flush=True)


class AmbiguousAlignmentGroup:

	"""
	Represents a group of ambiguous alignments of a single read/read pair.
	bwa -A assigns a primary read (pair) and flags all others as secondary alignments (0x100)
	due to the ngless filtering, we also have the case that the primary was filtered out

	Caveat: paired-end information is currently not considered for ambiguous alignment groups.
	This means that overlapping mates will result in duplicate counts.
	"""

	def __init__(self, aln):
		self.secondaries = list() # these are the secondary alignments
		self.primary1, self.primary2 = None, None
		self.qname = aln[0]
		self.uniq_alignments = set() # this is the set of alignments that can be annotated
		self.unannotated = 0
		self.add_alignment(aln)

	def add_alignment(self, aln):
		qname, flag = aln[0], aln[-1]
		short_aln = tuple(aln[2:])
		if short_aln[0] == -1:
			self.unannotated += 1
		elif flag & FIRST_IN_PAIR_FLAG and self.primary1 is None:
			self.primary1 = short_aln
		elif flag & SECOND_IN_PAIR_FLAG and self.primary2 is None:
			self.primary2 = short_aln
		else:
			self.secondaries.append(short_aln)
		if short_aln[0] != -1:
			self.uniq_alignments.add(short_aln[:-1])

	def n_align(self):
		return len(self.uniq_alignments)

	def resolve(self, counter, gff_dbm, bam, distmode="all1"):
		hits = dict()

		if self.primary1 is not None and self.primary2 is not None and self.primary1[:-1] == self.primary2[:-1]:
			self.primary2 = None

		alignments = set([self.primary1, self.primary2]).union(self.secondaries).difference({None})
		for rid, start, end, flag in alignments:
			hits.setdefault(rid, set()).add((start, end, flag & REVCOMP_ALIGNMENT))
		counter.update_ambiguous_counts(hits, self.n_align(), self.unannotated, gff_dbm, bam, feat_distmode=distmode)
