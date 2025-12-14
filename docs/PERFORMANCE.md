# Performance Optimizations

## Speed Improvements Implemented

### 1. **SSH Compression (SFTP only)**
- Enabled `compress=True` in SSH connection
- Compresses data during transfer
- Especially effective for text files (HTML, CSS, JS, JSON, etc.)
- **Expected speedup**: 2-5x for compressible files

### 2. **Smart Directory Caching**
- Caches created directories in memory (set)
- Avoids redundant `stat()` and `mkdir()` calls
- Thread-safe with locking mechanism
- **Expected speedup**: 10-50% depending on directory structure

### 3. **Parallel Uploads**
- Uses `ThreadPoolExecutor` for concurrent file uploads
- Default: 5 parallel workers (configurable with `--max-workers`)
- Each worker has its own FTP/SFTP connection
- Thread-safe progress tracking
- **Expected speedup**: 3-5x with default settings

### 4. **FTP Passive Mode (PASV)**
- Enabled by default for better firewall/NAT compatibility
- Client initiates all connections (no incoming ports needed)
- More reliable than active mode in modern networks
- Use `--ftp-active` flag to switch to active mode if needed
- **Benefit**: Better reliability and fewer connection failures

### 5. **Configuration**
You can customize the number of parallel workers:
```bash
# Use default (5 workers)
gsupload *.css

# Use more workers for faster uploads (if server allows)
gsupload --max-workers=10 *.css

# Use fewer workers for unstable connections
gsupload --max-workers=1 *.css
```

## Protocol-Specific Optimizations

### SFTP
✅ SSH compression  
✅ Directory caching  
✅ Parallel uploads (each worker has its own SSH connection)  
✅ Better error handling with SSHClient

### FTP
✅ Passive mode (PASV) by default  
✅ Directory caching  
✅ Parallel uploads (each worker has its own FTP connection)  
❌ Compression (not supported by FTP protocol)

## Benchmarking Tips

Compare before/after with the same files:
```bash
# Sequential (old behavior)
time gsupload --max-workers=1 *.css

# Parallel with compression (new default, 5 workers)
time gsupload *.css
```

## Expected Results

For typical web projects:
- **Small files (< 100KB)**: 3-5x faster (parallelism wins)
- **Large text files**: 4-7x faster (compression + parallelism)
- **Binary files**: 3-5x faster (parallelism only)
- **Many small files**: 4-6x faster (directory caching + parallelism)

Actual results depend on:
- Network latency
- Server performance
- File types and sizes
- Number of directories

## Notes

- More workers isn't always better (diminishing returns after 5-7)
- Some servers limit concurrent connections
- Use `--max-workers=1` to disable parallelism for debugging
