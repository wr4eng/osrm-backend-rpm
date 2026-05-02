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

BuildRequires:  cmake
BuildRequires:  gcc-c++
BuildRequires:  pkgconf-pkg-config
BuildRequires:  expat-devel
BuildRequires:  bzip2-devel
BuildRequires:  systemd-rpm-macros
BuildRequires:  boost-devel
BuildRequires:  lua-devel
BuildRequires:  fmt-devel
BuildRequires:  zlib-devel
BuildRequires: tbb-devel
BuildRequires: python3

Requires:       boost178-devel
Requires:       lua
Requires:       tbb
Requires:       fmt
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

python3 - << 'PYEOF'
import re, pathlib

path = pathlib.Path("include/util/json_container.hpp")
src  = path.read_text()

src = re.sub(
    r'// fwd\. decls\.\nstruct Object;\nstruct Array;\n',
    '// Forward-declare Value so Object/Array can be fully defined first.\nstruct Value;\n',
    src,
)

src = re.sub(
    r'using Value = std::variant<[^;]+>;\n',
    '',
    src,
)

src = src.replace(
    'std::unordered_map<std::string_view, Value>',
    'std::unordered_map<std::string, Value>',
)

insertion = (
    '\n'
    '// Value is a named struct inheriting std::variant so that:\n'
    '//  1. Its forward declaration above lets Object/Array use it by value.\n'
    '//  2. Object and Array are complete types by the time the variant is\n'
    '//     instantiated here, satisfying GCC 11 libstdc++ requirements.\n'
    '//  3. std::visit dispatches through the variant base; all existing\n'
    '//     Renderer<> operator()(const T&) overloads continue to match.\n'
    'struct Value : std::variant<String, Number, Object, Array, True, False, Null>\n'
    '{\n'
    '    using variant::variant;\n'
    '    using variant::operator=;\n'
    '};\n'
)

src = re.sub(
    r'(struct Array\s*\{[^}]*\};)',
    r'\1' + insertion,
    src,
    flags=re.DOTALL,
)

path.write_text(src)
print("json_container.hpp patched successfully.")
PYEOF

%build
export OSMIUM_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/libosmium-2.20.0/include
export SOL2_INCLUDE_DIR=%{_builddir}/%{name}-%{version}/sol2-3.3.0/include

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
    -DCMAKE_CXX_STANDARD=17 \
    -DCMAKE_CXX_STANDARD_REQUIRED=ON \
    -DCMAKE_CXX_FLAGS="%{optflags} -std=c++17 -Wno-maybe-uninitialized" \
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
- Replace brittle unified-diff Patch3 with an inline Python rewrite.
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-4
- Force C++20 via -DCMAKE_CXX_STANDARD=20 and -std=c++20 to fix std::variant
  template instantiation failures in EXTRACTOR target on GCC 11 (RHEL 9)
* Sat May 02 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-3
- EL9-only build using bundled libosmium and sol2 via external sources
- Removed RHEL 8 and Fedora conditionals
* Fri May 01 2026 W. Hadi HSW <wra.eng@gmail.com> - 26.4.1-1
- Initial package for EPEL 9
