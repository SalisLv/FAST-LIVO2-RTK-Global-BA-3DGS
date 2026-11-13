FROM bag-to-3dgs-train:local
RUN python -m pip install --no-cache-dir scipy==1.17.1 matplotlib==3.11.2
