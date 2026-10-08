# Changelog

## Repository preparation

### Unsmooth Skin Weights 1.2.1

- Restore command source formatting.
- Use physical influence indices for bulk weight access.
- Validate options and reject multi-mesh selection.
- Include the original window module with shorter English labels and help text.
- Replace the installer path fallback with `runpy` execution.
- Back up existing files instead of flushing the undo queue and force-unloading the plug-in.

### Multi Weight Transfer

- Restore source formatting and translate the window, messages and comments to English.
- Use full mesh and influence paths to resolve names.
- Match influences by name rather than index order.
- Keep temporary source cleanup available if source preparation fails.
- Preserve scene selection and close the undo chunk in cleanup.
- Use floor-based spatial cells for seam matching.
- Validate methods, thresholds, mesh inputs and seam master.
- Simplify the window layout; list entries remain the set processed by Transfer.
- Correct the documentation to describe master-based seam copying.
