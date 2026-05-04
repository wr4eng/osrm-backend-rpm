Name:           osrm-backend
Version:        26.4.1
Release:        7%{?dist}
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

Requires:       boost >= 1.70
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
in C++17 designed to run on OpenStreetMap data. It supports various routing
services via HTTP API and C++ library interface including Route, Table,
Nearest, Match, Trip, and Tile.

%prep
%autosetup -p1 -n %{name}-%{version}

## Neutralize -Werror in all CMake files
#grep -rl --include="CMakeLists.txt" --include="*.cmake" "\-Werror" . | \
#    xargs sed -i 's/-Werror\b/-Wno-error/g'

## Fix missing <unistd.h> in io-benchmark.cpp — POSIX functions write/read/close/lseek
sed -i '1s|^|#include <unistd.h>\n|' src/tools/io-benchmark.cpp

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

%install
%cmake_install

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
* Sun May 03 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-6
- Rebuild without Neutralize -Werror in all CMake files
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-5
- Fix missing #include <unistd.h> in tools/io-benchmark.cpp; POSIX functions
  write/read/close/lseek are undeclared without it on GCC with strict headers
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-4
- Fedora-only build using system libosmium >= 2.23.1 and sol2 >= 3.5.0
- Removed RHEL 8, RHEL 9, and all platform conditionals
