# Contact-site gallery: input health

Test rows: 1470; columns: 21; memory: 3663319 bytes.
Exact duplicate rows: 0; unique row IDs: 1470.

                      column   dtype  missing  unique
                      row_id  object        0    1470
                      source  object        0       1
                       split  object        0       1
            peptide_sequence  object        0      11
             target_sequence  object        0       5
                       label   int64        0       2
                    endpoint  object        0       1
                    group_id  object        0       4
               residue_index   int64        0     467
                structure_id  object        0      12
                      pdb_id  object        0      12
                   target_id  object        0       5
             observed_target  object        0      10
              source_row_ids  object        0      12
              source_studies  object        0       7
                  label_kind  object        0       1
          evaluation_stratum  object        0       1
minimum_heavyatom_distance_A float64        0    1470
               metadata_path  object        0      12
             metadata_sha256  object        0      12
           target_amino_acid  object        0      20

            label  residue_index  minimum_heavyatom_distance_A
count  1470.00000    1470.000000                   1470.000000
mean      0.14898     169.709524                     11.034343
std       0.35619     147.260421                      5.471572
min       0.00000      23.000000                      2.246286
25%       0.00000      61.000000                      6.666096
50%       0.00000      98.000000                     10.699100
75%       0.00000     276.750000                     14.406352
max       1.00000     501.000000                     28.218809

All 12 test complexes are included in lexical structure-ID order. No example is selected by performance.
Every displayed residue maps exactly once to the source target sequence; indices are 1-based source-sequence positions, not PDB residue numbers.
Geometric labels equal minimum peptide-to-target heavy-atom distance <=5 Angstrom. Only observed target residues are labeled.
No row is deleted or relabeled. Missing/unobserved parts of full target proteins are not negative labels.
Normality, VIF, outlier deletion and hypothesis tests are inapplicable to a descriptive visualization of fixed predictions.
Distance is checked only against reference labels and never passed to a prediction model.