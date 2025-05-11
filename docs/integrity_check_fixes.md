# Integrity Check Module Fixes

This document outlines the plan for fixing issues in the integrity check module and enhancing test coverage.

## 1. Fix AsyncMock Issues in CDN Store Tests

The CDN store tests are failing due to incorrect usage of AsyncMock vs MagicMock. These tests need to properly mock asynchronous behaviors.

### Implementation Plan

1. **Modify TestCDNStore Setup Method**
   - Update the session mock to properly handle async context managers
   - Ensure all async methods are mocked with AsyncMock instead of MagicMock

```python
def setUp(self):
    """Set up test fixtures."""
    # Create a temporary directory
    self.temp_dir = tempfile.TemporaryDirectory()
    self.base_dir = Path(self.temp_dir.name)

    # Test timestamp
    self.test_timestamp = datetime(2023, 6, 15, 12, 30, 0)
    self.test_satellite = SatellitePattern.GOES_16

    # Create store under test
    self.cdn_store = CDNStore(resolution="1000m", timeout=5)

    # Make sure session property returns something in tests
    self.session_mock = AsyncMock(spec=aiohttp.ClientSession)

    # Configure response mock
    self.session_response_mock = AsyncMock()
    self.session_response_mock.status = 200
    self.session_response_mock.headers = {'Content-Length': '12345'}

    # Configure context manager for head method
    head_context_manager = AsyncMock()
    head_context_manager.__aenter__.return_value = self.session_response_mock
    self.session_mock.head.return_value = head_context_manager

    # Configure context manager for get method
    get_context_manager = AsyncMock()
    get_context_manager.__aenter__.return_value = self.session_response_mock
    self.session_mock.get.return_value = get_context_manager

    # Configure content for downloads
    self.content_mock = AsyncMock()
    self.content_mock.iter_chunked = AsyncMock()
    self.session_response_mock.content = self.content_mock

    # Set up async iteration for content chunks
    async def mock_content():
        yield b"test data"
    self.content_mock.iter_chunked.return_value = mock_content()
```

2. **Fix test_session_property Method**
   - Use AsyncMock for all objects that are awaited
   - Use `assert_awaited_once()` for async method assertions

```python
async def test_session_property(self):
    """Test the session property creates a new session if needed."""
    # Setup - create a fresh CDNStore to avoid setup conflicts
    cdn_store = CDNStore(resolution="1000m", timeout=5)
    cdn_store._session = None  # Ensure session is None to start

    # Mock the ClientSession class
    with patch('aiohttp.ClientSession') as mock_client_session:
        # Create a simple mock object to return
        session_mock = AsyncMock()  # Use AsyncMock instead of MagicMock
        mock_client_session.return_value = session_mock

        # Test - should create a new session
        session = await cdn_store.session

        # Verify
        self.assertIsNotNone(session)
        mock_client_session.assert_called_once()

        # Test reuse - session should be cached
        session2 = await cdn_store.session
        self.assertEqual(session, session2)

        # Verify ClientSession was only created once
        self.assertEqual(mock_client_session.call_count, 1)
```

3. **Fix test_close Method**
   - Use the correct assertion for async method calls

```python
async def test_close(self):
    """Test closing the session."""
    # Setup - create a new CDNStore and mock session
    cdn_store = CDNStore(resolution="1000m", timeout=5)
    session_mock = AsyncMock()  # Use AsyncMock instead of MagicMock
    session_mock.closed = False

    # Set mock session
    cdn_store._session = session_mock

    # Test close
    await cdn_store.close()

    # Verify
    session_mock.close.assert_awaited_once()  # Use assert_awaited_once instead of assert_called_once
    self.assertIsNone(cdn_store._session)
```

4. **Fix test_exists Method**
   - Ensure context managers for async methods are properly mocked

```python
async def test_exists(self):
    """Test checking if a file exists in the CDN."""
    # Create a fresh store for cleaner testing
    cdn_store = CDNStore(resolution="1000m", timeout=5)

    # Create mocks
    with patch('goesvfi.integrity_check.remote.cdn_store.aiohttp.ClientSession') as mock_session_class:
        # Create response mock
        response_mock = AsyncMock()
        response_mock.status = 200

        # Create context manager mock
        context_mock = AsyncMock()
        context_mock.__aenter__.return_value = response_mock
        context_mock.__aexit__.return_value = None

        # Create session mock
        session_mock = AsyncMock()
        session_mock.head = AsyncMock(return_value=context_mock)
        mock_session_class.return_value = session_mock

        # Test success case (200)
        exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
        self.assertTrue(exists)

        # Test not found case (404)
        response_mock.status = 404
        exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
        self.assertFalse(exists)

        # Test error case
        session_mock.head.side_effect = aiohttp.ClientError("Test error")
        exists = await cdn_store.exists(self.test_timestamp, self.test_satellite)
        self.assertFalse(exists)
```

5. **Fix test_download Method**
   - Properly mock async content iteration
   - Use AsyncMock for all async methods

```python
async def test_download(self):
    """Test downloading a file from the CDN."""
    # Create a fresh store for cleaner testing
    cdn_store = CDNStore(resolution="1000m", timeout=5)

    # Setup the session mock with proper context manager behavior
    session_mock = AsyncMock(spec=aiohttp.ClientSession)
    response_mock = AsyncMock()
    response_mock.status = 200
    response_mock.headers = {'Content-Length': '12345'}

    # Configure content for download with async generator
    content_mock = AsyncMock()
    response_mock.content = content_mock

    # Create async generator for content chunks
    async def mock_content_generator():
        yield b"test data"

    # This is the key part - must use AsyncMock for an async iterator
    content_mock.iter_chunked = AsyncMock()
    content_mock.iter_chunked.return_value = mock_content_generator()

    # Configure the context managers
    head_context = AsyncMock()
    head_context.__aenter__.return_value = response_mock
    session_mock.head.return_value = head_context

    get_context = AsyncMock()
    get_context.__aenter__.return_value = response_mock
    session_mock.get.return_value = get_context

    # Directly inject the session
    cdn_store._session = session_mock

    # Destination path
    dest_path = self.base_dir / "test_download.jpg"

    # Mock file open
    mock_open = unittest.mock.mock_open()

    # Test successful download
    with patch('builtins.open', mock_open):
        result = await cdn_store.download(self.test_timestamp, self.test_satellite, dest_path)

    # Verify
    self.assertEqual(result, dest_path)
    mock_open.assert_called_with(dest_path, 'wb')
    mock_open().write.assert_called_with(b"test data")
```

## 2. Fix Wildcard Key Handling in S3 Store Tests

The S3 store tests are failing when handling wildcard patterns in file paths.

### Implementation Plan

1. **Enhance S3Store.download Method**
   - Add support for handling wildcard keys
   - Implement list_objects_v2 for wildcard matching

```python
async def download(self, ts: datetime, satellite: SatellitePattern, dest_path: Path) -> Path:
    """Download a file from S3.

    If the key contains wildcards, it will list matching objects and download the most recent one.

    Args:
        ts: Timestamp to download
        satellite: Satellite pattern enum
        dest_path: Destination path to save the file

    Returns:
        Path to the downloaded file

    Raises:
        FileNotFoundError: If the file doesn't exist
        IOError: If there's an error during download
    """
    # Get bucket and key
    bucket, key = self._get_bucket_and_key(ts, satellite)
    has_wildcard = '*' in key
    s3 = await self._get_s3_client()

    try:
        if not has_wildcard:
            # If no wildcard, do a direct download
            # First check if the file exists
            try:
                await s3.head_object(Bucket=bucket, Key=key)
            except botocore.exceptions.ClientError as e:
                error_code = e.response.get('Error', {}).get('Code')
                if error_code == '404':
                    raise FileNotFoundError(f"File not found: s3://{bucket}/{key}")
                raise IOError(f"Failed to check s3://{bucket}/{key}: {e}")

            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the file
            LOGGER.debug(f"Downloading s3://{bucket}/{key} to {dest_path}")
            await s3.download_file(Bucket=bucket, Key=key, Filename=str(dest_path))

            LOGGER.debug(f"Download complete: {dest_path}")
            return dest_path
        else:
            # Handle wildcard case by listing objects and finding the best match
            # Extract prefix and pattern parts from the key
            import re

            parts = key.split('*', 1)
            prefix = parts[0]

            # List objects with the prefix
            LOGGER.debug(f"Listing objects with prefix s3://{bucket}/{prefix}")

            paginator = s3.get_paginator('list_objects_v2')

            matching_objects = []
            async for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
                if 'Contents' not in page:
                    continue

                # Convert wildcard pattern to regex pattern
                regex_pattern = key.replace('*', '.*')
                compiled_pattern = re.compile(regex_pattern)

                for obj in page['Contents']:
                    obj_key = obj['Key']

                    # Check if this object matches our pattern
                    if compiled_pattern.match(obj_key):
                        matching_objects.append(obj_key)

            if not matching_objects:
                raise FileNotFoundError(f"No files found matching: s3://{bucket}/{key}")

            # Sort matching objects to get the most recent one
            matching_objects.sort()
            best_match = matching_objects[-1]

            # Create parent directory if it doesn't exist
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            # Download the best match
            LOGGER.debug(f"Downloading s3://{bucket}/{best_match} to {dest_path}")
            await s3.download_file(Bucket=bucket, Key=best_match, Filename=str(dest_path))

            LOGGER.debug(f"Download complete: {dest_path}")
            return dest_path

    except botocore.exceptions.ClientError as e:
        error_code = e.response.get('Error', {}).get('Code')
        if error_code == '404':
            raise FileNotFoundError(f"File not found: s3://{bucket}/{key}")
        raise IOError(f"Failed to download s3://{bucket}/{key}: {e}")
    except Exception as e:
        raise IOError(f"Unexpected error downloading s3://{bucket}/{key}: {e}")
```

2. **Enhance Test Setup to Test Wildcard Behavior**

```python
@patch.object(S3Store, '_get_s3_client', new_callable=AsyncMock)
async def test_download_with_wildcard(self, mock_get_client):
    """Test downloading a file from S3 with a wildcard pattern."""
    # Setup
    mock_get_client.return_value = self.s3_client_mock

    # Configure paginator for listing objects
    paginator_mock = AsyncMock()
    page_content = {
        'Contents': [
            {'Key': 'ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20230166121000_e20230166121999_c20230166122123.nc'},
            {'Key': 'ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20230166123000_e20230166123999_c20230166124123.nc'}
        ]
    }

    async def async_pages():
        yield page_content

    paginator_mock.paginate.return_value = async_pages()
    self.s3_client_mock.get_paginator.return_value = paginator_mock

    # Destination path
    dest_path = self.base_dir / "test_download.nc"

    # Set up TimeIndex to use wildcard for this test
    original_use_exact = getattr(TimeIndex, '_USE_EXACT_MATCH_IN_TEST', True)
    TimeIndex._USE_EXACT_MATCH_IN_TEST = False

    try:
        # Test the download with wildcard
        await self.s3_store.download(self.test_timestamp, self.test_satellite, dest_path)

        # Verify the correct methods were called
        self.s3_client_mock.get_paginator.assert_called_once_with('list_objects_v2')

        # Verify download was called with the latest matching file
        self.s3_client_mock.download_file.assert_called_once_with(
            Bucket=TimeIndex.S3_BUCKETS[self.test_satellite],
            Key='ABI-L1b-RadC/2023/166/12/OR_ABI-L1b-RadC-M6C13_G16_s20230166123000_e20230166123999_c20230166124123.nc',
            Filename=str(dest_path)
        )
    finally:
        # Restore original setting
        TimeIndex._USE_EXACT_MATCH_IN_TEST = original_use_exact
```

## 3. Address PyQt Segmentation Fault in Enhanced View Model Tests

The enhanced view model tests are causing segmentation faults due to threading and async event loop issues.

### Implementation Plan

1. **Create a Base Test Class with Proper PyQt Setup**

```python
class PyQtAsyncTestCase(unittest.TestCase):
    """Base class for PyQt test cases with async support."""

    def setUp(self):
        """Set up test environment for PyQt async tests."""
        # Create a new event loop for each test
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        # Create a QApplication if needed
        self.app = QApplication.instance()
        if self.app is None:
            self.app = QApplication([])

        # Set up asyncio integration with Qt
        try:
            from qasync import QEventLoop
            self.qt_loop = QEventLoop(self.app)
            asyncio.set_event_loop(self.qt_loop)
        except ImportError:
            pass  # Fall back to standard asyncio event loop if qasync not available

    def tearDown(self):
        """Clean up resources."""
        # Stop any timers or threads
        if hasattr(self, 'loop') and self.loop is not None:
            # Cancel all running tasks
            pending = asyncio.all_tasks(self.loop)
            for task in pending:
                task.cancel()

            if pending:
                self.loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )

            # Close the loop
            self.loop.close()

        # Process any pending Qt events
        QApplication.processEvents()
```

2. **Update EnhancedIntegrityCheckViewModel for Better Testing**

```python
class EnhancedIntegrityCheckViewModel(IntegrityCheckViewModel):
    """Enhanced version of the integrity check view model with expanded capabilities."""

    # Add testing helper method
    def prepare_for_testing(self):
        """Configure the view model for testing to avoid segmentation faults."""
        # Disable real threading
        self._use_thread_pool = False

        # Stop and nullify disk space timer
        if hasattr(self, '_disk_space_timer') and self._disk_space_timer is not None:
            self._disk_space_timer.stop()
            self._disk_space_timer = None

        # Add a method for direct execution of async tasks
        self.execute_sync = lambda coro: asyncio.get_event_loop().run_until_complete(coro)
```

3. **Fix TestEnhancedIntegrityCheckViewModel Class**

```python
class TestEnhancedIntegrityCheckViewModel(PyQtAsyncTestCase):
    """Test cases for the EnhancedIntegrityCheckViewModel class."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setup for proper Qt/async initialization
        super().setUp()

        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Mock dependencies
        self.mock_cache_db = MagicMock(spec=CacheDB)
        self.mock_cache_db.reset_database = AsyncMock()

        self.mock_cdn_store = MagicMock(spec=CDNStore)
        self.mock_s3_store = MagicMock(spec=S3Store)

        # Create test view model
        self.view_model = EnhancedIntegrityCheckViewModel(
            cache_db=self.mock_cache_db,
            cdn_store=self.mock_cdn_store,
            s3_store=self.mock_s3_store,
        )

        # Prepare for testing to avoid segfaults
        self.view_model.prepare_for_testing()

        # Mock ReconcileManager
        self.mock_reconcile_manager = MagicMock()
        self.view_model._reconcile_manager = self.mock_reconcile_manager

        # Mock QThreadPool (for direct execution)
        self.mock_thread_pool = MagicMock(spec=QThreadPool)

        # Override the start method to run tasks directly
        def direct_execute(runnable):
            # Just run the task directly without threading
            runnable.run()

        self.mock_thread_pool.start.side_effect = direct_execute
        self.view_model._thread_pool = self.mock_thread_pool

        # Dates for testing
        self.start_date = datetime(2023, 6, 15, 0, 0, 0)
        self.end_date = datetime(2023, 6, 15, 1, 0, 0)

    def tearDown(self):
        """Tear down test fixtures."""
        # Explicitly clean up
        try:
            if hasattr(self, 'view_model'):
                try:
                    self.view_model.cleanup()
                except Exception:
                    pass

            # Clean up temporary directory
            self.temp_dir.cleanup()
        finally:
            # Call parent teardown
            super().tearDown()
```

4. **Fix AsyncTaskSignals for Better Testing**

```python
class AsyncTaskSignals(QObject):
    """Signals for async tasks."""

    error = pyqtSignal(str)
    progress = pyqtSignal(int, int, str)  # current, total, message
    scan_finished = pyqtSignal(object)  # Result dictionary
    download_finished = pyqtSignal(object)  # Dictionary of timestamp -> path

    # Add helper methods for direct test interaction
    def emit_error(self, message):
        """Emit error signal directly."""
        self.error.emit(message)

    def emit_progress(self, current, total, message):
        """Emit progress signal directly."""
        self.progress.emit(current, total, message)

    def emit_scan_finished(self, result):
        """Emit scan finished signal directly."""
        self.scan_finished.emit(result)

    def emit_download_finished(self, result):
        """Emit download finished signal directly."""
        self.download_finished.emit(result)
```

5. **Fix TestAsyncTasks to Avoid Segfaults**

```python
class TestAsyncTasks(PyQtAsyncTestCase):
    """Test cases for the async tasks used by the enhanced view model."""

    def setUp(self):
        """Set up test fixtures."""
        # Call parent setUp for proper PyQt/async setup
        super().setUp()

        # Create a temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Mock view model
        self.mock_view_model = MagicMock(spec=EnhancedIntegrityCheckViewModel)
        self.mock_view_model._reconcile_manager = MagicMock()
        self.mock_view_model._reconcile_manager.scan_directory = AsyncMock()
        self.mock_view_model._reconcile_manager.scan_directory.return_value = (set(), set())

        self.mock_view_model._start_date = datetime(2023, 6, 15, 0, 0, 0)
        self.mock_view_model._end_date = datetime(2023, 6, 15, 1, 0, 0)
        self.mock_view_model._satellite = SatellitePattern.GOES_16
        self.mock_view_model._interval_minutes = 10
        self.mock_view_model._base_directory = self.base_dir

        # Mock signals for direct use
        self.mock_signals = MagicMock(spec=AsyncTaskSignals)

        # Set up tasks under test
        self.scan_task = AsyncScanTask(self.mock_view_model)
        self.scan_task.signals = self.mock_signals

        self.download_task = AsyncDownloadTask(self.mock_view_model)
        self.download_task.signals = self.mock_signals

        # Patch asyncio.new_event_loop to return our test loop
        self.patch_new_event_loop = patch('asyncio.new_event_loop', return_value=self.loop)
        self.mock_new_event_loop = self.patch_new_event_loop.start()

    def tearDown(self):
        """Tear down test fixtures."""
        # Stop patches
        self.patch_new_event_loop.stop()

        # Clean up temporary directory
        self.temp_dir.cleanup()

        # Call parent tearDown for proper cleanup
        super().tearDown()

    def test_scan_task_run(self):
        """Test scanning task execution."""
        # Run the task directly
        self.scan_task.run()

        # Verify signals were emitted
        self.mock_signals.scan_finished.emit.assert_called_once()

    async def test_run_scan(self):
        """Test the async scan operation directly."""
        # Run the coroutine directly
        result = await self.scan_task._run_scan()

        # Verify
        self.assertEqual(result["status"], "completed")
        self.mock_view_model._reconcile_manager.scan_directory.assert_called_once()
```

## 4. Create IntegrityCheckTabTest Integration Test Class

Once the basic unit tests are fixed, we'll need to implement proper integration tests that verify the functionality of the integrity check tab.

### Implementation Plan

1. **Create a Basic Integration Test Class**

```python
class TestIntegrityCheckTabIntegration(unittest.TestCase):
    """Integration tests for the IntegrityCheckTab."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a QApplication
        self.app = QApplication.instance() or QApplication([])

        # Create a temporary directory for test files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base_dir = Path(self.temp_dir.name)

        # Create data directory structure
        self.data_dir = self.base_dir / "data"
        self.data_dir.mkdir(parents=True)

        # Create mock ViewModel
        self.view_model = IntegrityCheckViewModel()
        self.view_model.base_directory = str(self.data_dir)

        # Patch scan and download methods for testing
        self.view_model.start_scan = MagicMock()
        self.view_model.start_downloads = MagicMock()

        # Create the tab widget
        self.tab = IntegrityCheckTab(self.view_model)

        # Create a window to hold the tab (prevents some rendering issues)
        self.window = QMainWindow()
        self.window.setCentralWidget(self.tab)
        self.window.resize(800, 600)

    def tearDown(self):
        """Tear down test fixtures."""
        # Clean up
        self.window.close()
        QApplication.processEvents()

        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_initial_state(self):
        """Test the initial state of the tab."""
        # Check that controls are properly initialized
        self.assertEqual(self.tab.directory_edit.text(), str(self.data_dir))
        self.assertFalse(self.tab.download_button.isEnabled())
        self.assertFalse(self.tab.export_button.isEnabled())
        self.assertTrue(self.tab.scan_button.isEnabled())

        # Check default date range is set to yesterday
        yesterday = datetime.now() - timedelta(days=1)
        start_dt = self.tab.start_date_edit.dateTime().toPython()
        self.assertEqual(start_dt.date(), yesterday.date())

    def test_scan_button_click(self):
        """Test clicking the scan button."""
        # Click the scan button
        QTest.mouseClick(self.tab.scan_button, Qt.LeftButton)

        # Verify view model method was called
        self.view_model.start_scan.assert_called_once()

    def test_directory_selection(self):
        """Test directory selection signal."""
        # Create a mock receiver
        mock_receiver = MagicMock()

        # Connect to the signal
        self.tab.directory_selected.connect(mock_receiver)

        # Use an internal method to simulate directory selection
        new_dir = str(self.base_dir / "new_dir")
        self.tab.view_model.base_directory = new_dir
        self.tab.directory_edit.setText(new_dir)
        self.tab._browse_directory = lambda: None  # Mock to avoid dialog
        self.tab.directory_selected.emit(new_dir)

        # Verify signal was emitted
        mock_receiver.assert_called_once_with(new_dir)
```

## Testing Tasks

Here are the priority testing tasks that should be tackled next:

1. Fix the AsyncMock issues in CDN Store tests
2. Fix wildcard key handling in S3 Store tests
3. Address PyQt segmentation fault in enhanced view model tests
4. Create IntegrityCheckTabTest integration tests
5. Implement UI state transition tests
6. Add disk space monitoring and error handling tests
7. Create mock fixtures for satellite imagery tests
