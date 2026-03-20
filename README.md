
# HalfFrame Separator

## 概要

1つのフレームに2つの写真が収まったハーフ判の写真を個別の画像に分割するPythonツールです。  
あなたのOLYMPUS PENやPENTAX 17や他の楽しいハーフ判カメラたちともっと仲良くなれることを期待しています。

## 依存ライブラリ

- PIL (pillow)
- NumPy
- SciPy

## 使い方

```bash
python halfframe.py <入力ディレクトリ> [--outdir 出力ディレクトリ] [--threshold 値] [--dilation 値] [--erosion 値]
```

境界の認識に失敗した場合は、つながったままの画像で出てきます。

### 引数

- `indir`: ソース画像ディレクトリ（必須）
- `--outdir, -o`: 出力画像ディレクトリ（オプション、デフォルト: `{indir}_separated`）
- `--threshold, -t`: フレーム間隔を検出するための暗さの閾値（デフォルト: 64）
- `--dilation, -d`: スムージング用の膨張反復回数（デフォルト: 7）
- `--erosion, -e`: スムージング用の収縮反復回数（デフォルト: 14）

### 対応フォーマット

JPEG, TIFF

### 現状の制約

- EXIF情報の引き継ぎにはまだ対応していません。
- 処理の並列化はそのうち対応します。
- 一度画像をデコードし、処理を行った後再エンコードするので、画質劣化があるかも……。

## 生成AIの使用について

コーディング・ドキュメント執筆に部分的にGitHub Copilotを活用しています。

---

# HalfFrame Separator

## Overview

This is a Python tool that splits half-frame photos, which contain two pictures in one frame, into individual images.  
We hope you can enjoy your OLYMPUS PEN, PENTAX 17, and other fun half-frame cameras even more.

## Dependencies

- PIL (pillow)
- NumPy
- SciPy

## Usage

```bash
python halfframe.py <input_directory> [--outdir output_directory] [--threshold value] [--dilation value] [--erosion value]
```

If boundary recognition fails, the images may come out connected.

### Arguments

- `indir`: Source image directory (required)
- `--outdir, -o`: Output image directory (optional, default: `{indir}_separated`)
- `--threshold, -t`: Darkness threshold for detecting frame intervals (default: 64)
- `--dilation, -d`: Number of dilation iterations for smoothing (default: 7)
- `--erosion, -e`: Number of erosion iterations for smoothing (default: 14)

### Supported Formats

JPEG, TIFF

### Current Limitations

- EXIF information transfer is not yet supported.
- Parallel processing will be supported in the future.
- There may be a loss of quality since images are decoded, processed, and then re-encoded.

## Use of Generative AI

We partially utilize GitHub Copilot for coding and document writing.

