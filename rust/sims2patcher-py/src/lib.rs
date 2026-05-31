use pyo3::exceptions::{PyRuntimeError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::PyDict;

use sims2patcher_core::{
    patch_fontstyle_ini, patch_package, ImageFilter, PatchOptions, PatchStats, ProgressEvent,
    StorageMode,
};

#[pyclass]
struct PyPatchResult {
    #[pyo3(get)]
    processed_entries: usize,
    #[pyo3(get)]
    modified_entries: usize,
    #[pyo3(get)]
    skipped_entries: usize,
    #[pyo3(get)]
    warnings: Vec<String>,
}

impl From<PatchStats> for PyPatchResult {
    fn from(stats: PatchStats) -> Self {
        Self {
            processed_entries: stats.processed_entries,
            modified_entries: stats.modified_entries,
            skipped_entries: stats.skipped_entries,
            warnings: stats.warnings,
        }
    }
}

#[pyfunction]
fn patch_dbpf_package(
    py: Python<'_>,
    source_path: String,
    target_path: String,
    filename: String,
    options: &Bound<'_, PyDict>,
    progress_callback: Py<PyAny>,
) -> PyResult<PyPatchResult> {
    let options = parse_options(options)?;
    let callback = progress_callback;

    py.allow_threads(move || {
        patch_package(source_path, target_path, &filename, options, |event| {
            let _ = Python::with_gil(|py| call_progress(py, &callback, event));
        })
    })
    .map(PyPatchResult::from)
    .map_err(to_py_error)
}

#[pyfunction]
fn patch_fontstyle(source_path: String, target_path: String, scale: f32) -> PyResult<()> {
    patch_fontstyle_ini(source_path, target_path, scale).map_err(to_py_error)
}

fn parse_options(options: &Bound<'_, PyDict>) -> PyResult<PatchOptions> {
    let mut parsed = PatchOptions::default();

    if let Some(value) = options.get_item("scale")? {
        parsed.scale = value.extract::<f32>()?;
    }
    if let Some(value) = options.get_item("threads")? {
        parsed.threads = value.extract::<usize>()?.max(1);
    }
    if let Some(value) = options.get_item("loading_screen_fps")? {
        parsed.loading_screen_fps = value.extract::<u32>()?;
    }
    if let Some(value) = options.get_item("qfs_level")? {
        parsed.qfs_level = value.extract::<usize>()?.max(2);
    }
    if let Some(value) = options.get_item("verify_compression")? {
        parsed.verify_compression = value.extract::<bool>()?;
    }
    if let Some(value) = options.get_item("storage")? {
        parsed.storage = match value.extract::<String>()?.as_str() {
            "fast" | "fast-compatible" | "uncompressed" => StorageMode::FastCompatible,
            "compact" | "compressed" => StorageMode::Compact,
            "none" => StorageMode::None,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown storage mode: {other}"
                )))
            }
        };
    }
    if let Some(value) = options.get_item("image_filter")? {
        parsed.image_filter = match value.extract::<String>()?.as_str() {
            "nearest" => ImageFilter::Nearest,
            "hamming" => ImageFilter::Hamming,
            "linear" => ImageFilter::Linear,
            "cubic" => ImageFilter::Cubic,
            "lanczos" => ImageFilter::Lanczos,
            other => {
                return Err(PyValueError::new_err(format!(
                    "unknown image filter: {other}"
                )))
            }
        };
    }

    Ok(parsed)
}

fn call_progress(py: Python<'_>, callback: &Py<PyAny>, event: ProgressEvent) -> PyResult<()> {
    callback.call1(py, (event.current, event.total, event.message))?;
    Ok(())
}

fn to_py_error(error: sims2patcher_core::PatchError) -> PyErr {
    PyRuntimeError::new_err(error.to_string())
}

#[pymodule]
fn sims2patcher_rust(module: &Bound<'_, PyModule>) -> PyResult<()> {
    module.add_class::<PyPatchResult>()?;
    module.add_function(wrap_pyfunction!(patch_dbpf_package, module)?)?;
    module.add_function(wrap_pyfunction!(patch_fontstyle, module)?)?;
    Ok(())
}
