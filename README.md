# OSRM Backend - Quick Start Guide

This guide will help you set up and run OSRM Backend on your system.

## Prerequisites

- OSRM Backend installed via RPM
- OSM data file in PBF format (download from https://download.geofabrik.de/)
- Sufficient disk space (processing requires 10-50x the PBF file size)
- Sufficient RAM (recommended: 2GB RAM per 100MB PBF file)

## Step 1: Download OSM Data

Download the region you need from Geofabrik:

```bash
# Example: Download Berlin data
cd /tmp
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf

# Other examples:
# Indonesia: https://download.geofabrik.de/asia/indonesia-latest.osm.pbf
# Java: https://download.geofabrik.de/asia/indonesia/jawa-latest.osm.pbf
# West Java: https://download.geofabrik.de/asia/indonesia/jawa/jawa-barat-latest.osm.pbf
```

## Step 2: Choose a Routing Profile

OSRM comes with several pre-configured profiles in `/usr/share/osrm/profiles/`:

- `car.lua` - Car routing (default, recommended for most use cases)
- `bicycle.lua` - Bicycle routing
- `foot.lua` - Pedestrian routing

```bash
# View available profiles
ls -l /usr/share/osrm/profiles/
```

## Step 3: Process the OSM Data

The OSRM processing pipeline has three stages:

### 3.1 Extract - Parse OSM data and apply routing profile

```bash
# Choose your dataset name (must match DATASET_NAME in config)
DATASET_NAME="berlin-latest"

# Extract with car profile
osrm-extract \
    -p /usr/share/osrm/profiles/car.lua \
    /tmp/${DATASET_NAME}.osm.pbf

# This creates: ${DATASET_NAME}.osrm, .osrm.ebg, .osrm.nodes, etc.
```

**Processing time**: ~1-5 minutes per 100MB PBF (varies by CPU)

### 3.2 Partition - Create the MLD partition

```bash
# Partition the graph (required for MLD algorithm)
osrm-partition ${DATASET_NAME}.osrm

# This creates: ${DATASET_NAME}.osrm.partition, .osrm.cells
```

**Processing time**: ~5-30 minutes depending on data size

### 3.3 Customize - Prepare routing data

```bash
# Customize the partitioned graph
osrm-customize ${DATASET_NAME}.osrm

# This creates: ${DATASET_NAME}.osrm.cell_metrics, .osrm.mldgr
```

**Processing time**: ~1-10 minutes depending on data size

## Step 4: Move Processed Data

Move all generated files to the OSRM data directory:

```bash
# Move all OSRM files to the data directory
sudo mv ${DATASET_NAME}.osrm* /var/lib/osrm/

# Set correct ownership
sudo chown -R osrm:osrm /var/lib/osrm/

# Verify files are present
ls -lh /var/lib/osrm/
```

**Important**: All files must have the same base name (e.g., `berlin-latest.osrm*`)

## Step 5: Configure the Service

Edit the configuration file to match your dataset name:

```bash
sudo vi /etc/sysconfig/osrm-backend
```

Update the `DATASET_NAME` to match your processed files (without the `.osrm` extension):

```bash
# /etc/sysconfig/osrm-backend

# Dataset name (matches your .osrm files prefix)
DATASET_NAME=berlin-latest

# Routing algorithm: MLD (recommended) or CH
ALGORITHM=MLD

# Network binding
BIND_IP=127.0.0.1  # Change to 0.0.0.0 to allow external access
BIND_PORT=5000

# Performance tuning
THREADS=4  # Adjust based on your CPU cores
MAX_VIA=50
MAX_TABLE=100
MAX_NEAREST=100

# Additional osrm-routed flags
EXTRA_ARGS="--compression=true"
```

**Configuration Tips**:
- `DATASET_NAME`: Must match your `.osrm` file basename exactly
- `BIND_IP`: Use `127.0.0.1` for local-only access, `0.0.0.0` for network access
- `THREADS`: Set to number of CPU cores for best performance
- `ALGORITHM`: MLD is faster and recommended; CH uses less memory

## Step 6: Start the Service

Enable and start the OSRM service:

```bash
# Enable service to start on boot
sudo systemctl enable osrm-backend.service

# Start the service
sudo systemctl start osrm-backend.service

# Check status
sudo systemctl status osrm-backend.service

# View logs
sudo journalctl -u osrm-backend.service -f
```

## Step 7: Test the API

Test that OSRM is responding:

```bash
# Health check
curl http://127.0.0.1:5000/health

# Example route query (Berlin coordinates)
# From Alexanderplatz to Brandenburg Gate
curl "http://127.0.0.1:5000/route/v1/driving/13.4124,52.5206;13.3777,52.5163?overview=false"

# Example with full geometry
curl "http://127.0.0.1:5000/route/v1/driving/13.4124,52.5206;13.3777,52.5163?overview=full&geometries=geojson"
```

**For Indonesian coordinates example** (if using Indonesia data):

```bash
# Jakarta: Monas to Bundaran HI
curl "http://127.0.0.1:5000/route/v1/driving/106.8271,6.1754;106.8227,6.1951?overview=full"

# Bandung: Gedung Sate to Braga Street
curl "http://127.0.0.1:5000/route/v1/driving/107.6186,-6.9024;107.6089,-6.9175?overview=full"
```

## Complete Example Workflow

Here's a complete example for processing West Java data:

```bash
# 1. Download data
cd /tmp
wget https://download.geofabrik.de/asia/indonesia/jawa/jawa-barat-latest.osm.pbf

# 2. Process the data
DATASET="jawa-barat-latest"
osrm-extract -p /usr/share/osrm/profiles/car.lua ${DATASET}.osm.pbf
osrm-partition ${DATASET}.osrm
osrm-customize ${DATASET}.osrm

# 3. Deploy
sudo mv ${DATASET}.osrm* /var/lib/osrm/
sudo chown -R osrm:osrm /var/lib/osrm/

# 4. Configure
sudo sed -i 's/DATASET_NAME=.*/DATASET_NAME=jawa-barat-latest/' /etc/sysconfig/osrm-backend

# 5. Restart service
sudo systemctl restart osrm-backend.service

# 6. Test
curl "http://127.0.0.1:5000/route/v1/driving/107.6186,-6.9024;107.6089,-6.9175?overview=false"
```

## Troubleshooting

### Service won't start

```bash
# Check logs for errors
sudo journalctl -u osrm-backend.service -n 50

# Common issues:
# - DATASET_NAME doesn't match files in /var/lib/osrm/
# - Missing .osrm files
# - Wrong file permissions
```

### Permission denied errors

```bash
# Fix ownership
sudo chown -R osrm:osrm /var/lib/osrm/
sudo chown -R osrm:osrm /var/log/osrm/
```

### Port already in use

```bash
# Check what's using port 5000
sudo ss -tlnp | grep 5000

# Change port in /etc/sysconfig/osrm-backend
sudo vi /etc/sysconfig/osrm-backend
# Update BIND_PORT=5001
sudo systemctl restart osrm-backend.service
```

### Memory issues during processing

For large datasets, you may need to increase swap space or use a machine with more RAM:

```bash
# Check memory usage during processing
free -h
top
```

## API Documentation

Full API documentation: http://project-osrm.org/docs/v5.24.0/api/

Common endpoints:
- `/route/v1/{profile}/{coordinates}` - Calculate routes
- `/table/v1/{profile}/{coordinates}` - Distance/duration matrix
- `/match/v1/{profile}/{coordinates}` - Map matching
- `/nearest/v1/{profile}/{coordinate}` - Nearest street
- `/trip/v1/{profile}/{coordinates}` - Round trip (TSP)

## Updating Data

To update your routing data:

```bash
# 1. Download new PBF file
wget https://download.geofabrik.de/europe/germany/berlin-latest.osm.pbf

# 2. Process it (same steps as above)
osrm-extract -p /usr/share/osrm/profiles/car.lua berlin-latest.osm.pbf
osrm-partition berlin-latest.osrm
osrm-customize berlin-latest.osrm

# 3. Stop service
sudo systemctl stop osrm-backend.service

# 4. Replace files
sudo rm /var/lib/osrm/berlin-latest.osrm*
sudo mv berlin-latest.osrm* /var/lib/osrm/
sudo chown -R osrm:osrm /var/lib/osrm/

# 5. Start service
sudo systemctl start osrm-backend.service
```

## Performance Tuning

### For production use:

1. **Increase file descriptors** in service file (already set to 65536)
2. **Tune threads**: Set `THREADS` to match CPU cores
3. **Adjust limits**: Modify `MAX_TABLE`, `MAX_VIA` based on your use case
4. **Enable compression**: Keep `--compression=true` for reduced memory usage
5. **Use MLD algorithm**: Faster than CH for most use cases

### Firewall configuration (if allowing external access):

```bash
# Open port 5000
sudo firewall-cmd --permanent --add-port=5000/tcp
sudo firewall-cmd --reload
```

## Additional Resources

- Official documentation: https://github.com/Project-OSRM/osrm-backend/wiki
- API reference: http://project-osrm.org/docs/v5.24.0/api/
- Download OSM data: https://download.geofabrik.de/
- OSRM demo: http://map.project-osrm.org/

## References
- GitHub: https://github.com/Project-OSRM/osrm-backend/issues
- COPR: https://copr.fedorainfracloud.org/coprs/whhsw/osrm-backend/
- Mailing list: https://lists.openstreetmap.org/listinfo/osrm-talk