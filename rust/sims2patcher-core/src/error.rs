use thiserror::Error;

pub type Result<T> = std::result::Result<T, PatchError>;

#[derive(Debug, Error)]
pub enum PatchError {
    #[error("array too small")]
    ArrayTooSmall,

    #[error("file too large for QFS compression: {0} bytes")]
    FileTooLarge(usize),

    #[error("invalid QFS magic header")]
    InvalidMagicHeader,

    #[error("invalid DBPF package: {0}")]
    InvalidDbpf(String),

    #[error("unsupported by Rust patcher: {0}")]
    Unsupported(String),

    #[error("image error: {0}")]
    Image(#[from] image::ImageError),

    #[error("I/O error: {0}")]
    Io(#[from] std::io::Error),

    #[error("UTF-8 error: {0}")]
    Utf8(#[from] std::string::FromUtf8Error),

    #[error("parse integer error: {0}")]
    ParseInt(#[from] std::num::ParseIntError),

    #[error("parse float error: {0}")]
    ParseFloat(#[from] std::num::ParseFloatError),
}
