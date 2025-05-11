# Settings Persistence Issues

## Current Status
Despite multiple fixes to the QSettings implementation, settings (particularly input directory and crop rectangle) are not being persisted between application restarts.

## Fixes Attempted

1. **Fixed QSettings Inconsistency**
   - Made QSettings application and organization names consistent between QApplication-level settings and individual QSettings objects
   - Updated `app.setApplicationName("GOES_VFI_App")` and `app.setOrganizationName("GOES_VFI")` to match MainWindow
   - Modified MainWindow to get these values from QApplication.instance() instead of hardcoding them

2. **Added Validation for Settings Location**
   - Added code to detect mismatched QSettings paths and auto-correct them
   - Added logging to help diagnose where settings are being saved
   - Logs confirm that settings are being saved to: `/Users/justin/Library/Preferences/com.goes-vfi.GOES_VFI_App.plist`

3. **Enhanced Settings Storage**
   - Added redundant storage with multiple keys (`paths/inputDirectory` and `inputDir`)
   - Modified key detection to check multiple possible keys when loading
   - Added extensive debugging to verify that settings are being written properly

4. **Added File Existence Verification**
   - Added code to check if the settings file exists after saving
   - Added file size checks to confirm settings are being written properly

## Observed Behavior
- Settings file is correctly created at: `/Users/justin/Library/Preferences/com.goes-vfi.GOES_VFI_App.plist`
- Debug logs confirm settings are being saved successfully
- Values appear to be verified correctly during save operations
- However, on application restart, settings are not being properly restored despite still existing in the file

## Next Steps to Investigate

1. **Platform-Specific Issues**
   - Verify if this is a macOS-specific issue with plist file permissions or format
   - Check if using INI format for settings might help (QSettings::IniFormat)

2. **Settings Loading Order**
   - Review the loading order to ensure settings are loaded after UI initialization
   - Investigate MainTab settings loading vs MainWindow settings loading

3. **Disconnection Between Values**
   - There may be a disconnect between the saved settings and where they're applied
   - Check that UI elements are properly updated when settings are loaded

4. **Data Transfer Issues**
   - There might be issues with the references between MainWindow and MainTab
   - Ensure values are properly transferred between components

5. **Preferences Cache Issues**
   - On macOS, investigate potential issues with Apple's preferences cache
   - Consider testing with `defaults delete com.goes-vfi.GOES_VFI_App` to clear the cache

## Current Workaround
Until this issue is resolved, users will need to select the input directory and crop settings each time the application is launched.
