FROM bag-to-3dgs-ros:local
RUN mkdir -p /usr/local/lib/cmake/Sophus \
    && printf '%s\n' 'set(Sophus_FOUND TRUE)' 'set(Sophus_INCLUDE_DIRS "/usr/local/include")' 'set(Sophus_LIBRARIES "/usr/local/lib/libSophus.so")' \
       > /usr/local/lib/cmake/Sophus/SophusConfig.cmake
