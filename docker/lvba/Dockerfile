FROM bag-to-3dgs-ros-dev:local
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
ENV DEBIAN_FRONTEND=noninteractive
RUN rm -f /etc/apt/sources.list.d/ros1-snapshots.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git freeglut3-dev \
       libgoogle-glog-dev libgflags-dev libsuitesparse-dev libglew-dev libsqlite3-dev colmap \
    && rm -rf /var/lib/apt/lists/*
COPY .deps/ceres-solver /opt/ceres-solver
RUN cmake -S /opt/ceres-solver -B /opt/ceres-build -DCMAKE_BUILD_TYPE=Release \
      -DBUILD_TESTING=OFF -DBUILD_EXAMPLES=OFF -DBUILD_BENCHMARKS=OFF \
      -DSCHUR_SPECIALIZATIONS=OFF -DCMAKE_CXX_FLAGS_RELEASE='-O1 -DNDEBUG' \
    && cmake --build /opt/ceres-build -j2 \
    && cmake --install /opt/ceres-build \
    && rm -rf /opt/ceres-build /opt/ceres-solver
