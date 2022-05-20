"""module docstring"""

from collections import Counter

from .region_counter import RegionCounter
from .seq_counter import UniqueSeqCounter, AmbiguousSeqCounter


class CountManager:
    # this may be counter-intuitive
    # but originates from the samflags 0x10, 0x20,
    # which also identify the reverse-strandness of the read
    # and not the forward-strandness
    PLUS_STRAND, MINUS_STRAND = False, True

    def __init__(
        # pylint: disable=W0613
        self, distribution_mode="1overN", region_counts=True, strand_specific=False
    ):
        self.distribution_mode = distribution_mode
        self.strand_specific = strand_specific

        self.uniq_seqcounts = UniqueSeqCounter(strand_specific=strand_specific)

        self.ambig_seqcounts = AmbiguousSeqCounter(
            strand_specific=strand_specific, distribution_mode=distribution_mode
        )

        self.uniq_regioncounts = RegionCounter(strand_specific=strand_specific)
        self.ambig_regioncounts = RegionCounter(
            strand_specific=strand_specific,
            distribution_mode=distribution_mode
        )

    @staticmethod
    def _windup_stream(stream):
        """Count data are coming in via generators.
        This function ensures that the generator is actually exhausted."""
        for _ in stream:
            ...

    def has_ambig_counts(self):
        return self.ambig_regioncounts or self.ambig_seqcounts

    def update_counts(self, count_stream, ambiguous_counts=False):
        seq_counter, region_counter = (
            (self.uniq_seqcounts, self.uniq_regioncounts)
            if not ambiguous_counts
            else (self.ambig_seqcounts, self.ambig_regioncounts)
        )
        stream = seq_counter.update_counts(count_stream)
        if region_counter is not None:
            stream = region_counter.update_counts(stream)

        CountManager._windup_stream(stream)

    def dump_raw_counters(self, prefix, bam):
        if self.uniq_seqcounts is not None:
            self.uniq_seqcounts.dump(prefix, bam)
        if self.ambig_seqcounts is not None:
            self.ambig_seqcounts.dump(prefix, bam)
        if self.uniq_regioncounts is not None:
            self.uniq_regioncounts.dump(prefix, bam)
        if self.ambig_regioncounts is not None:
            self.ambig_regioncounts.dump(prefix, bam)

    def get_unannotated_reads(self):
        if self.uniq_regioncounts:
            return sum((
                self.uniq_regioncounts.unannotated_reads,
                self.ambig_regioncounts.unannotated_reads
            ))

        return sum((
            self.uniq_seqcounts.unannotated_reads,
            self.ambig_seqcounts.unannotated_reads,
        ))

    def get_counts(self, seqid, region_counts=False, strand_specific=False):
        if region_counts:
            rid, seqid = seqid[0], seqid[1:]
            uniq_counter = self.uniq_regioncounts.get(rid, Counter())
            ambig_counter = self.ambig_regioncounts.get(rid, Counter())
        else:
            uniq_counter, ambig_counter = self.uniq_seqcounts, self.ambig_seqcounts

        if strand_specific:
            uniq_counts = [
                uniq_counter[(seqid, CountManager.PLUS_STRAND)],
                uniq_counter[(seqid, CountManager.MINUS_STRAND)],
            ]
            ambig_counts = [
                ambig_counter[(seqid, CountManager.PLUS_STRAND)],
                ambig_counter[(seqid, CountManager.MINUS_STRAND)],
            ]
        else:
            uniq_counts, ambig_counts = [uniq_counter[seqid]], [ambig_counter[seqid]]

        return uniq_counts, ambig_counts

    def get_regions(self, rid):
        return set(self.uniq_regioncounts.get(rid, set())).union(
            self.ambig_regioncounts.get(rid, set())
        )