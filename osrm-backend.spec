Name:           osrm-backend
Version:        26.4.1
Release:        3%{?dist}
Summary:        High performance routing engine for OpenStreetMap data

%undefine _lto_cflags

License:        BSD-2-Clause
URL:            https://github.com/Project-OSRM/osrm-backend
Source0:        https://github.com/Project-OSRM/osrm-backend/archive/refs/tags/v%{version}.tar.gz#/%{name}-%{version}.tar.gz
Source1:        osrm-backend.service
Source2:        osrm-backend.env

%if 0%{?rhel} == 8
Source10:       https://github.com/osmcode/libosmium/archive/refs/tags/v2.20.0.tar.gz#/libosmium-2.20.0.tar.gz
Source11:       https://github.com/ThePhD/sol2/archive/refs/tags/v3.3.0.tar.gz#/sol2-3.3.0.tar.gz
%endif

BuildRequires:  cmake >= 3.18
BuildRequires:  gcc-c++
BuildRequires:  pkgconf-pkg-config
BuildRequires:  expat-devel
BuildRequires:  bzip2-devel
BuildRequires:  systemd-rpm-macros

%if 0%{?rhel} == 8
# Use boost1.78 from EPEL 8 which provides proper CMake config files
BuildRequires:  boost1.78-devel
BuildRequires:  lua-devel >= 5.3
BuildRequires:  tbb-devel >= 2018
BuildRequires:  fmt-devel >= 6.0
%else
BuildRequires:  boost-devel >= 1.70
BuildRequires:  lua-devel >= 5.3
BuildRequires:  tbb-devel >= 2020
BuildRequires:  fmt-devel >= 8.0
%endif

%if 0%{?fedora}
BuildRequires:  libosmium-devel >= 2.16
BuildRequires:  sol2-devel >= 3.3
%endif

%if 0%{?rhel} == 8
Requires:       boost1.78
Requires:       lua >= 5.3
Requires:       tbb >= 2018
Requires:       fmt >= 6.0
%else
Requires:       boost >= 1.70
Requires:       lua >= 5.3
Requires:       tbb >= 2020
Requires:       fmt >= 8.0
%endif

Requires:       expat
Requires:       bzip2
Requires(pre):  shadow-utils

Provides:       user(osrm)
Provides:       group(osrm)

%description
Open Source Routing Machine (OSRM) is a high-performance routing engine written
in C++17 designed to run on OpenStreetMap data. It supports various routing
services via HTTP API and C++ library interface including Route, Table,
Nearest, Match, Trip, and Tile.

%prep
%autosetup -p1 -n %{name}-%{version}

%if 0%{?rhel} == 8
tar -xzf %{SOURCE10}
tar -xzf %{SOURCE11}

# Patch CMakeLists.txt to find boost1.78 from EPEL
# boost1.78 installs to /usr/lib64/boost1.78/ and /usr/include/boost1.78/
sed -i 's/find_package(Boost \([0-9.]*\) REQUIRED CONFIG/find_package(Boost 1.78 REQUIRED CONFIG/' CMakeLists.txt
%endif

# Neutralize -Werror in all CMake files
grep -rl --include="CMakeLists.txt" --include="*.cmake" "\-Werror" . | \
    xargs sed -i 's/-Werror\b/-Wno-error/g'

%build
%if 0%{?rhel} == 8
export OSMIUM_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/libosmium-2.20.0/include
export SOL2_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/sol2-3.3.0/include

# boost1.78 from EPEL installs cmake configs here
export BOOST178_CMAKE_DIR=/usr/lib64/boost1.78

mkdir -p %{_vpath_builddir}
cd %{_vpath_builddir}

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
    -DCMAKE_CXX_FLAGS="%{optflags} -Wno-maybe-uninitialized -I/usr/include/boost1.78" \
    -DCMAKE_PREFIX_PATH=/usr/lib64/boost1.78 \
    -DBoost_ROOT=/usr/lib64/boost1.78 \
    -DBOOST_INCLUDEDIR=/usr/include/boost1.78 \
    -DBOOST_LIBRARYDIR=/usr/lib64/boost1.78/lib \
    -DBoost_NO_SYSTEM_PATHS=ON \
    -Dlibosmium_INCLUDE_DIR=${OSMIUM_INCLUDE_DIR} \
    -Dsol2_INCLUDE_DIR=${SOL2_INCLUDE_DIR} \
    ..

%make_build
cd ..

%else
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
%endif

%install
%if 0%{?rhel} == 8
cd %{_vpath_builddir}
%make_install
cd ..
%else
%cmake_install
%endif

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
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-3
- Switch to boost1.78-devel from EPEL 8 for proper CMake config support
- Drop bundled Boost build in favor of EPEL package
* Fri May 01 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-1
- Initial package for Fedora and EPEL
