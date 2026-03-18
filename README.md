# dsss

Google Drive へローカルファイルを安全にアップロードするための Python ライブラリです。

ローカルファイルを直接Driveへ反映するのではなく、**処理の流れを明確に分離した設計（scan → plan → execute）**により、

* 誤ったフォルダへのアップロード
* 意図しないファイルの混入
* 処理の不透明化

を防ぐことを目的としています。

> dsss は「同期ツール」ではなく、「安全なアップロード処理ライブラリ」です。

---

## 目次

* 1. dsssとは
* 2. できること
* 3. 導入
* 4. 基本の使い方
* 5. API一覧
* 6. 処理フロー
* 7. 内部構造
* 8. ディレクトリ構成

---

## 1. dsssとは

### 基本思想

1. ローカルファイルを取得（scan）
2. アップロード対象を決定（plan）
3. Driveへ反映（execute）

この3段階により、処理の可視化と安全性を確保します。

---

## 2. できること

### できること

* 指定ディレクトリ直下のファイル取得
* JSTベースの日時処理
* 日付フォルダの自動生成
* Google Driveへのファイルアップロード

### 制約

* 再帰的なディレクトリ取得は行わない（直下のみ）
* Driveの削除・移動は行わない
* 同期機能（差分削除など）は提供しない

---

## 3. 導入

```bash
pip install -e .
```

依存ライブラリ（別途必要）

```bash
pip install google-api-python-client google-auth google-auth-oauthlib
```

---

## 4. 基本の使い方

```python
from dsss import UploaderWorkflow

workflow = UploaderWorkflow(
    local_dir="./data",
    root_folder_id="YOUR_FOLDER_ID",
)

result = workflow.run()

print(result)
```

---

## 5. API一覧

### メインAPI

#### UploaderWorkflow

```python
workflow = UploaderWorkflow(local_dir, root_folder_id)
workflow.run()
```

---

### Local Scan

#### scan_local_files

```python
from dsss import scan_local_files

files = scan_local_files("./data")
```

---

### 時刻処理

* JST
* to_jst
* is_within_range
* build_date_path

---

### データモデル

* LocalFile
* DriveFolder
* LocalScanResult
* UploadItemResult
* UploadRunResult

---

### 例外

* GDriveUploaderError
* ConfigError
* ValidationError
* LocalScanError
* DriveAccessError
* DuplicateDateFolderError
* UploadFailedError

---

## 6. 処理フロー

```text
Local Scan
   ↓
Plan生成
   ↓
Driveアップロード
   ↓
結果返却
```

---

## 7. 内部構造

### 構成

* workflow
* local_scan
* timeutils
* types
* errors

### 特徴

* 各機能をサブパッケージ単位で分離
* 依存関係を最小化
* テストしやすい設計

---

## 8. ディレクトリ構成

```text
dsss/
├── workflow/
├── local_scan/
├── timeutils/
├── types/
├── errors/
└── __init__.py
```

---

## ライセンス

MIT License
