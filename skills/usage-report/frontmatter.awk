BEGIN {for (i = 1; i < ARGC; i++) if ((getline x < ARGV[i]) < 0) delete ARGV[i]; else close(ARGV[i])}
FNR == 1 {n = k = 0; if (++f > 50) {left++; nextfile} print "== " FILENAME}
/^---\r?$/ {if (++n == 2) nextfile; next}
n == 1 && k++ < 15 {print substr($0, 1, 300)}
END {if (left) print "== " left " more files left out"}
