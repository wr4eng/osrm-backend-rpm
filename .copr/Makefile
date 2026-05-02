srpm:
	dnf install -y wget
	wget -O osrm-backend-26.4.1.tar.gz https://github.com/Project-OSRM/osrm-backend/archive/refs/tags/v26.4.1.tar.gz
	rpmbuild -bs --define "_sourcedir $(CURDIR)" \
	             --define "_specdir $(CURDIR)" \
	             --define "_builddir $(CURDIR)" \
	             --define "_srcrpmdir $(outdir)" \
	             --define "_rpmdir $(outdir)" \
	             osrm-backend.spec
