# Muscle-memory wrapper; the pipeline itself lives in the press package.
PRESS ?= python3 -m press

.PHONY: all check pdf epub html markdown site txt docx pages source verify verify-formats render wordcount clean

all check pdf epub html markdown site txt docx pages source verify verify-formats render wordcount clean:
	$(PRESS) $@
