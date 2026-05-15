Name:           osrm-backend
Version:        26.5.0
Release:        1%{?dist}
Summary:        High performance routing engine for OpenStreetMap data

%undefine _lto_cflags

License:        BSD-2-Clause
URL:            https://github.com/Project-OSRM/osrm-backend
Source0:        https://github.com/Project-OSRM/osrm-backend/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        osrm-backend.service
Source2:        osrm-backend.env

BuildRequires:  cmake >= 3.18
BuildRequires:  gcc-c++
BuildRequires:  pkgconf-pkg-config
BuildRequires:  expat-devel
BuildRequires:  bzip2-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  boost-devel >= 1.70
BuildRequires:  lua-devel >= 5.3
BuildRequires:  tbb-devel >= 2020
BuildRequires:  fmt-devel >= 8.0
BuildRequires:  libosmium-devel >= 2.23.1
BuildRequires:  sol2-devel >= 3.5.0
BuildRequires:  libarchive-devel >= 3.8.0

Requires:       boost >= 1.70
Requires:       lua >= 5.3
Requires:       tbb >= 2020
Requires:       fmt >= 8.0
Requires:       expat
Requires:       bzip2
Requires:       libarchive >= 3.8.0

Requires(pre):  shadow-utils
Provides:       user(osrm)
Provides:       group(osrm)

%description
Open Source Routing Machine (OSRM) is a high-performance routing engine written
in C++17 designed to run on OpenStreetMap data. It supports various routing
services via HTTP API and C++ library interface including Route, Table,
Nearest, Match, Trip, and Tile.


# ── devel subpackage 
%package        devel
Summary:        Development files for %{name}
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
Headers, unversioned shared-library symlink, and pkg-config file for
developing applications that link against the OSRM library.


# ── prep 
%prep
%autosetup -p1 -n %{name}-%{version}

# Fix missing <unistd.h> in io-benchmark.cpp
# POSIX functions write/read/close/lseek are undeclared without it
sed -i '1s|^|#include <unistd.h>\n|' src/tools/io-benchmark.cpp


# ── build 
%build
%cmake \
    -DCMAKE_BUILD_TYPE=Release \
    -DENABLE_CONAN=OFF \
    -DENABLE_NODE_BINDINGS=OFF \
    -DENABLE_LTO=OFF \
    -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF \
    -DCMAKE_SKIP_RPATH=ON \
    -DCMAKE_INSTALL_PREFIX=%{_prefix} \
    -DCMAKE_INSTALL_LIBDIR=%{_lib} \
    -DCMAKE_INSTALL_INCLUDEDIR=%{_includedir} \
    -DBUILD_TOOLS=ON \
    -DBUILD_LIBRARY=ON \
    -DCMAKE_CXX_FLAGS="%{optflags} -Wno-maybe-uninitialized"

%cmake_build

# ── post-build: inject SOVERSION into every installed .so ────────────────────
# Upstream does not set SOVERSION; we use the package major version (26).
# For each libfoo.so we produce libfoo.so.26.4.1 (real) and libfoo.so.26 (soname symlink).
# libfoo.so itself becomes the -devel unversioned symlink.


# ── install 
%install
%cmake_install

# Move lib → lib64 when cmake installed into the wrong place.
# We compare resolved paths so this is a no-op when they are the same.
_src=%{buildroot}%{_prefix}/lib
_dst=%{buildroot}%{_libdir}
if [ -d "$_src" ] && [ "$(readlink -f $_src)" != "$(readlink -f $_dst)" ]; then
    mkdir -p "$_dst"
    cp -a "$_src"/. "$_dst"/
    rm -rf "$_src"
fi

# ── Inject SOVERSION: upstream builds unversioned .so files only. ─────────────
# Fedora policy requires:
#   %{_libdir}/libfoo.so.X.Y.Z   – real shared object (main package)
#   %{_libdir}/libfoo.so.X       – soname symlink     (main package)
#   %{_libdir}/libfoo.so         – unversioned symlink (-devel package)
#
# We implement this by: rename the installed .so to .so.%{version}, then
# create the soname (.so.major) and unversioned (.so) symlinks.
_major=$(echo %{version} | cut -d. -f1)   # e.g. "26"
for _lib in %{buildroot}%{_libdir}/lib*.so; do
    [ -f "$_lib" ] || continue             # skip if glob is empty
    _base=${_lib%.so}                      # e.g. …/libosrm
    # real file
    mv "$_lib" "${_base}.so.%{version}"
    # soname symlink  libosrm.so.26 → libosrm.so.26.4.1
    ln -sf "$(basename ${_base}.so.%{version})" "${_base}.so.${_major}"
    # unversioned symlink  libosrm.so → libosrm.so.26
    ln -sf "$(basename ${_base}.so.${_major})" "${_lib}"
done

install -D -m 0644 %{SOURCE1} %{buildroot}%{_unitdir}/%{name}.service
install -D -m 0644 %{SOURCE2} %{buildroot}%{_sysconfdir}/sysconfig/%{name}

install -d -m 0755 %{buildroot}/var/lib/osrm
install -d -m 0755 %{buildroot}/var/log/osrm

install -m 0755 -d %{buildroot}%{_licensedir}/%{name}/
find %{_builddir}/%{name}-%{version} -maxdepth 1 -type f \
    \( -iname 'license*' -o -iname 'copying*' \) \
    -exec install -m 0644 -t %{buildroot}%{_licensedir}/%{name}/ {} +


# ── scriptlets 
%pre
getent group  osrm >/dev/null || groupadd -r osrm
getent passwd osrm >/dev/null || \
    useradd -r -g osrm -d /var/lib/osrm -s /sbin/nologin \
            -c "OSRM Backend service user" osrm
exit 0

%post
%systemd_post %{name}.service

%preun
%systemd_preun %{name}.service

%postun
%systemd_postun_with_restart %{name}.service
if [ $1 -eq 0 ]; then
    userdel  osrm 2>/dev/null || :
    groupdel osrm 2>/dev/null || :
fi


# ── file lists 

# Main package: binaries + versioned .so files
# libosrm.so.26.4.1  (real ELF shared object)
# libosrm.so.26      (soname symlink)
%files
%{_bindir}/osrm-extract
%{_bindir}/osrm-partition
%{_bindir}/osrm-customize
%{_bindir}/osrm-contract
%{_bindir}/osrm-routed
%{_bindir}/osrm-datastore
%{_bindir}/osrm-components
%{_bindir}/osrm-io-benchmark
%{_libdir}/libosrm*.so.*
%{_datadir}/osrm/
%{_unitdir}/%{name}.service
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%dir %attr(0755,osrm,osrm) /var/lib/osrm
%dir %attr(0755,osrm,osrm) /var/log/osrm
%doc README.md
%license %{_licensedir}/%{name}/


# -devel package: headers + unversioned .so symlinks + pkg-config
# libosrm.so  (unversioned symlink, needed only at link time with -losrm)
%files devel
%{_includedir}/osrm/
%{_includedir}/flatbuffers/
%{_libdir}/libosrm*.so
%{_libdir}/pkgconfig/libosrm.pc


# ── changelog 
%changelog
* Fri May 15 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.5.0-1
- Update 26.5.0 upstream

* Mon May 04 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-8
- Inject SOVERSION in %%install: rename upstream unversioned .so to
  .so.%%{version}, create soname symlink .so.MAJOR, keep .so as unversioned
  symlink for -devel; upstream CMake does not set SOVERSION at all
- Fix lib→lib64 mv: use readlink -f comparison instead of [ ! -d ] so the
  move actually fires on x86_64 where lib64 already exists
- %%files main: use libosrm*.so.* glob (versioned real files + soname symlinks)
- %%files devel: use libosrm*.so glob (unversioned symlinks only)

* Mon May 04 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-7
- Add -devel subpackage; move headers and unversioned .so symlink there
- Main package now owns only versioned .so files (libosrm.so.*)
- Fixes Fedora packaging policy violations:
    * Header files must be in -devel subpackage
    * Unversioned .so symlink must be in -devel subpackage
    * Versioned .so files go directly in %%{_libdir}

* Sun May 03 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-6
- Rebuild without Neutralize -Werror in all CMake files

* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-5
- Fix missing #include <unistd.h> in tools/io-benchmark.cpp; POSIX functions
  write/read/close/lseek are undeclared without it on GCC with strict headers

* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-4
- Fedora-only build using system libosmium >= 2.23.1 and sol2 >= 3.5.0
- Removed RHEL 8, RHEL 9, and all platform conditionals
