# Makefile

SPHINXBUILD   = sphinx-build
SPHINXPROJ    = MemoryScope-Doc
ASSETSDIR     = assets
BUILDDIR      = build/html
SOURCEDIR_EN  = en/source
BUILDDIR_EN   = build/html/en
SOURCEDIR_ZH  = zh/source
BUILDDIR_ZH   = build/html/zh

# English document
en:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR_EN)" "$(BUILDDIR_EN)"
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR_EN)"

# Chinese document
zh:
	@$(SPHINXBUILD) -b html "$(SOURCEDIR_ZH)" "$(BUILDDIR_ZH)"
	@echo
	@echo "Build finished. The HTML pages are in $(BUILDDIR_ZH)"

index:
	@cp "$(ASSETSDIR)/redirect.html" "$(BUILDDIR)/index.html"

%: Makefile
	@$(SPHINXBUILD) -M $@ "$(SOURCEDIR_EN)" "$(BUILDDIR_EN)" $(O)

all: en zh index

.PHONY: all en zh index