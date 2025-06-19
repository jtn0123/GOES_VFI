# Batch Processing Guide

The GOES-VFI application includes a powerful batch processing system that allows you to queue and process multiple video interpolation jobs automatically.

## Features

- **Priority Queue**: Jobs are processed based on priority (Urgent, High, Normal, Low)
- **Concurrent Processing**: Configure how many jobs run simultaneously
- **Persistent Queue**: Jobs are saved and restored between application sessions
- **Progress Tracking**: Real-time progress updates for each job
- **Error Recovery**: Failed jobs can be retried or cleared
- **Directory Processing**: Process entire directories of images at once

## Using the Batch Processing Tab

### Adding Jobs

1. **Select Input Files**:
   - Click "Add Files..." to select individual image sequences
   - Click "Add Folder..." to add all images from a directory

2. **Set Output Directory**:
   - Click "Select..." to choose where processed videos will be saved
   - Each job will create a uniquely named output file

3. **Choose Priority**:
   - Urgent: Process immediately
   - High: Process before normal jobs
   - Normal: Standard priority (default)
   - Low: Process when queue is otherwise empty

4. **Add to Queue**:
   - Click "Add to Queue" to create jobs from selected inputs

### Managing the Queue

- **Start/Stop Processing**: Control when jobs are processed
- **Concurrent Jobs**: Adjust how many jobs run at once (1-4)
- **Cancel Jobs**: Remove pending jobs from the queue
- **Clear Completed**: Remove finished jobs to clean up the display

### Queue Display

The queue table shows:
- **Name**: Job description
- **Status**: Pending, Running, Completed, Failed, or Cancelled
- **Priority**: Job priority level
- **Progress**: Percentage complete for running jobs
- **Created**: When the job was added
- **Duration**: Processing time
- **Actions**: Cancel button for pending jobs

## Programmatic Usage

### Basic Example

```python
from goesvfi.pipeline.batch_queue import (
    BatchJob, BatchProcessor, JobPriority
)

# Create processor
processor = BatchProcessor()

# Create queue with your processing function
queue = processor.create_queue(
    process_function=my_process_function,
    max_concurrent=2
)

# Create a job
job = BatchJob(
    id="unique_id",
    name="My Video",
    input_path=Path("/path/to/input.png"),
    output_path=Path("/path/to/output.mp4"),
    settings={"target_fps": 30},
    priority=JobPriority.NORMAL
)

# Add to queue
queue.add_job(job)

# Start processing
queue.start()
```

### Processing a Directory

```python
# Add all PNG files from a directory
job_ids = processor.add_directory(
    input_dir=Path("/path/to/images"),
    output_dir=Path("/path/to/output"),
    settings={"target_fps": 60},
    pattern="*.png",
    recursive=True,
    priority=JobPriority.HIGH
)
```

### Monitoring Progress

```python
# Connect to signals
queue.job_started.connect(on_job_started)
queue.job_progress.connect(on_job_progress)
queue.job_completed.connect(on_job_completed)
queue.job_failed.connect(on_job_failed)

def on_job_progress(job_id: str, progress: float):
    print(f"Job {job_id}: {progress:.1f}% complete")
```

## Resource Management

Batch processing respects the resource limits configured in the Resource Limits tab:
- Memory usage limits
- CPU usage limits
- Processing time limits

Jobs that exceed limits will be automatically terminated and marked as failed.

## Queue Persistence

The batch queue is automatically saved to:
- Linux/macOS: `~/.config/goesvfi/batch_queue.json`
- Windows: `%APPDATA%\goesvfi\batch_queue.json`

When you restart the application:
- Completed and cancelled jobs are preserved
- Running jobs are reset to pending
- The queue resumes processing automatically

## Best Practices

1. **Organize Input Files**: Group related sequences in directories
2. **Set Appropriate Priorities**: Use high priority for urgent jobs
3. **Monitor Resources**: Watch system resources when increasing concurrent jobs
4. **Regular Cleanup**: Clear completed jobs periodically
5. **Check Settings**: Ensure FFmpeg and RIFE settings are configured before batch processing

## Troubleshooting

### Jobs Failing

- Check the error message in the queue display
- Verify input files exist and are valid images
- Ensure output directory has write permissions
- Check system resources (memory, disk space)

### Slow Processing

- Reduce concurrent jobs if system is overloaded
- Check Resource Limits settings
- Consider processing smaller batches

### Queue Not Persisting

- Check file permissions for config directory
- Ensure adequate disk space
- Look for errors in application logs
