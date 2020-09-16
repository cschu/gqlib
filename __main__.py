import argparse
import os
import pathlib

from gffquant.feature_quantifier import FeatureQuantifier

def main():
	ap = argparse.ArgumentParser()
	ap.add_argument("gff_file", type=str)
	ap.add_argument("bam_file", type=str)
	ap.add_argument("--out_prefix", "-o", type=str, default="gffquant")
	ap.add_argument("--count_config", type=str)
	ap.add_argument("--name_sorted_bam", "-n", default=None)
	args = ap.parse_args()

	gff_index = args.gff_file + ".index"

	if os.path.dirname(args.out_prefix):
		pathlib.Path(os.path.dirname(args.out_prefix)).mkdir(exist_ok=True, parents=True)


	if not os.path.exists(args.gff_file):
		raise ValueError("gff database does not exist", args.gff_file)
	if not os.path.exists(gff_index):
		raise ValueError("gff index does not exist", gff_index)
	if not os.path.exists(args.bam_file):
		raise ValueError("bam file does not exist", args.bam_file)

	fq = FeatureQuantifier(
		args.gff_file,
		gff_index,
		count_config=args.count_config
	)
	fq.process_data(args.bam_file, out_prefix=args.out_prefix, bamfile_ns=args.name_sorted_bam)


if __name__ == "__main__":
	main()
