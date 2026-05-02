Name:           osrm-backend
Version:        26.4.1
Release:        5%{?dist}
Summary:        High performance routing engine for OpenStreetMap data

%undefine _lto_cflags

License:        BSD-2-Clause
URL:            https://github.com/Project-OSRM/osrm-backend
Source0:        https://github.com/Project-OSRM/osrm-backend/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        osrm-backend.service
Source2:        osrm-backend.env
Source10:       https://github.com/osmcode/libosmium/archive/refs/tags/v2.20.0.tar.gz#/libosmium-2.20.0.tar.gz
Source11:       https://github.com/ThePhD/sol2/archive/refs/tags/v3.3.0.tar.gz#/sol2-3.3.0.tar.gz

# GCC 11 (RHEL 9) does not support incomplete types as std::variant alternatives.
# json_container.hpp forward-declares Object/Array then immediately defines
#   using Value = std::variant<..., Object, Array, ...>
# before those structs are complete, causing "too many initializers" and
# "no match for operator=" in the EXTRACTOR target.
# Fix: forward-declare Value as a named struct, define Object/Array fully
# (std::vector<Value>/unordered_map<string,Value> are fine with an incomplete
# value type), then define Value as a struct inheriting the variant so
# std::visit and all Renderer<> overloads work without any API change.
# Also changes the Object map key from std::string_view to std::string, which
# is a correctness fix (owning map must not hold non-owning keys).
Patch3:         osrm-backend-gcc11-variant.patch

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
BuildRequires:  zlib-devel

Requires:       boost >= 1.75
Requires:       lua >= 5.3
Requires:       tbb >= 2020
Requires:       fmt >= 8.0
Requires:       expat
Requires:       bzip2
Requires(pre):  shadow-utils

Provides:       user(osrm)
Provides:       group(osrm)

%description
Open Source Routing Machine (OSRM) is a high-performance routing engine written
in C++17/C++20 designed to run on OpenStreetMap data. It supports various
routing services via HTTP API and C++ library interface including Route, Table,
Nearest, Match, Trip, and Tile.

%prep
%autosetup -p1 -n %{name}-%{version}

tar -xzf %{SOURCE10}
tar -xzf %{SOURCE11}

# Neutralize -Werror in all CMake files
grep -rl --include="CMakeLists.txt" --include="*.cmake" "\-Werror" . | \
    xargs sed -i 's/-Werror\b/-Wno-error/g'

%build
export OSMIUM_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/libosmium-2.20.0/include
export SOL2_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/sol2-3.3.0/include

mkdir -p %{_vpath_builddir}
cd %{_vpath_builddir}

# OSRM 26.x requires C++20 for several features. The variant patch above makes
# json_container.hpp compile on GCC 11 without relying on GCC 12+ / libstdc++
# improvements to std::variant with incomplete types.
%{__cmake} \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_C_FLAGS_RELEASE:STRING="-DNDEBUG" \
    -DCMAKE_CXX_FLAGS_RELEASE:STRING="-DNDEBUG" \
    -DCMAKE_INSTALL_PREFIX:PATH=%{_prefix} \
    -DCMAKE_INSTALL_LIBDIR:PATH=%{_libdir} \
    -DCMAKE_INSTALL_INCLUDEDIR:PATH=%{_includedir} \
    -DENABLE_CONAN=OFF \
    -DENABLE_NODE_BINDINGS=OFF \
    -DENABLE_LTO=OFF \
    -DCMAKE_INTERPROCEDURAL_OPTIMIZATION=OFF \
    -DCMAKE_SKIP_RPATH=ON \
    -DBUILD_TOOLS=ON \
    -DBUILD_LIBRARY=ON \
    -DCMAKE_CXX_STANDARD=20 \
    -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -DCMAKE_CXX_FLAGS="%{optflags} -std=c++20 -Wno-maybe-uninitialized" \
    -Dlibosmium_INCLUDE_DIR=${OSMIUM_INCLUDE_DIR} \
    -Dsol2_INCLUDE_DIR=${SOL2_INCLUDE_DIR} \
    ..

%make_build
cd ..

%install
cd %{_vpath_builddir}
%make_install
cd ..

# Move libraries from lib to lib64 if needed
if [ -d %{buildroot}%{_prefix}/lib ] && [ ! -d %{buildroot}%{_libdir} ]; then
    mkdir -p %{buildroot}%{_libdir}
    mv %{buildroot}%{_prefix}/lib/* %{buildroot}%{_libdir}/
    rmdir %{buildroot}%{_prefix}/lib
fi

install -D -m 0644 %{SOURCE1} %{buildroot}%{_unitdir}/%{name}.service
install -D -m 0644 %{SOURCE2} %{buildroot}%{_sysconfdir}/sysconfig/%{name}
install -d -m 0755 %{buildroot}/var/lib/osrm
install -d -m 0755 %{buildroot}/var/log/osrm

install -m 0755 -d %{buildroot}%{_licensedir}/%{name}/
find %{_builddir}/%{name}-%{version} -maxdepth 1 -type f \( -iname 'license*' -o -iname 'copying*' \) \
    -exec install -m 0644 -t %{buildroot}%{_licensedir}/%{name}/ {} +

%pre
getent group osrm >/dev/null || groupadd -r osrm
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
    userdel osrm 2>/dev/null || :
    groupdel osrm 2>/dev/null || :
fi

%files
%{_bindir}/osrm-extract
%{_bindir}/osrm-partition
%{_bindir}/osrm-customize
%{_bindir}/osrm-contract
%{_bindir}/osrm-routed
%{_bindir}/osrm-datastore
%{_bindir}/osrm-components
%{_bindir}/osrm-io-benchmark
%{_libdir}/libosrm*.so
%{_libdir}/pkgconfig/libosrm.pc
%{_includedir}/osrm/
%{_includedir}/flatbuffers/
%{_datadir}/osrm/
%{_unitdir}/%{name}.service
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%dir %attr(0755,osrm,osrm) /var/lib/osrm
%dir %attr(0755,osrm,osrm) /var/log/osrm
%doc README.md
%license %{_licensedir}/%{name}/

%changelog
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-5
- Add Patch3: osrm-backend-gcc11-variant.patch
  Fix std::variant instantiation failure on GCC 11 (RHEL 9/EL9):
  json_container.hpp defined Object/Array as incomplete types at the point
  std::variant was instantiated, causing "too many initializers" and
  "no match for operator=" errors in the EXTRACTOR target.
  Restructure: forward-declare Value as a named struct, define Object/Array
  fully before the variant, then define Value inheriting std::variant so
  std::visit and all Renderer<> call-sites work without API changes.
  Also fixes Object key type from std::string_view to std::string (correctness).
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-4
- Force C++20 via -DCMAKE_CXX_STANDARD=20 and -std=c++20 to fix std::variant
  template instantiation failures in EXTRACTOR target on GCC 11 (RHEL 9)
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-3
- EL9-only build using bundled libosmium and sol2 via external sources
- Removed RHEL 8 and Fedora conditionals
* Fri May 01 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-1
- Initial package for EPEL 9
