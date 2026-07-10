"""
文档处理 API（T1 集成 - 2026-06-01）

提供 3 个端点：
  POST /api/v1/document/extract-tables   提取 PDF/DOCX 表格 → Markdown
  POST /api/v1/document/ocr              图片 OCR 识别
  POST /api/v1/document/clean            文档页眉页脚清理
"""
import os
import logging
import tempfile
from pathlib import Path

from flask import Blueprint, request, jsonify

from app.services.service_manager import get_unified_manager

logger = logging.getLogger(__name__)

document_api = Blueprint('document_api', __name__, url_prefix='/api/v1/document')


def _save_upload(file_storage, suffix: str) -> str:
    """保存上传文件到临时目录，返回文件路径"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    file_storage.save(tmp.name)
    return tmp.name


@document_api.route('/extract-tables', methods=['POST'])
def extract_tables():
    """
    提取 PDF/DOCX 中的表格

    接受 multipart/form-data 上传文件（file 字段）
    可选参数：format=markdown|json
    """
    try:
        manager = get_unified_manager()
        if not manager.structured_processor:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'PROCESSOR_UNAVAILABLE',
                    'message': 'StructuredDataProcessor 未初始化（缺少 pypdf/python-docx）'
                }
            }), 503

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': {'code': 'NO_FILE', 'message': '缺少 file 字段'}
            }), 400

        f = request.files['file']
        suffix = Path(f.filename).suffix.lower() or '.pdf'
        if suffix not in ('.pdf', '.docx', '.doc'):
            return jsonify({
                'success': False,
                'error': {'code': 'UNSUPPORTED_FORMAT', 'message': f'不支持的格式: {suffix}'}
            }), 400

        tmp_path = _save_upload(f, suffix)
        try:
            output_format = request.form.get('format', 'markdown').lower()

            if suffix in ('.pdf',):
                tables = manager.structured_processor.extract_pdf_tables(tmp_path)
            else:
                tables = manager.structured_processor.extract_docx_tables(tmp_path)

            if output_format == 'json':
                payload = [
                    {
                        'table_index': t.table_index,
                        'headers': t.headers,
                        'rows': t.rows,
                        'source': t.source,
                        'page_number': t.page_number,
                    }
                    for t in tables
                ]
            else:
                payload = [manager.structured_processor.table_to_markdown(t) for t in tables]

            return jsonify({
                'success': True,
                'data': {
                    'file_name': f.filename,
                    'format': output_format,
                    'table_count': len(tables),
                    'tables': payload,
                }
            })
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as e:
        logger.error(f"extract_tables 失败: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'EXTRACT_FAILED', 'message': str(e)}
        }), 500


@document_api.route('/ocr', methods=['POST'])
def ocr_image():
    """
    图片 OCR 识别

    接受 multipart/form-data 上传图片（file 字段，jpg/png/bmp/webp）
    可选参数：language=chi_sim+eng (默认)
    """
    try:
        manager = get_unified_manager()
        if not manager.ocr_processor:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'OCR_UNAVAILABLE',
                    'message': 'OCR 处理器未初始化（请安装 pytesseract/easyocr/paddleocr）'
                }
            }), 503

        if not manager.ocr_processor._ocr_available:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'NO_OCR_BACKEND',
                    'message': '未安装任何 OCR 后端（pytesseract/easyocr/paddleocr 之一）'
                }
            }), 503

        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'error': {'code': 'NO_FILE', 'message': '缺少 file 字段'}
            }), 400

        f = request.files['file']
        suffix = Path(f.filename).suffix.lower() or '.png'
        if suffix not in ('.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff'):
            return jsonify({
                'success': False,
                'error': {'code': 'UNSUPPORTED_FORMAT', 'message': f'不支持的图片格式: {suffix}'}
            }), 400

        language = request.form.get('language', 'chi_sim+eng')
        tmp_path = _save_upload(f, suffix)
        try:
            result = manager.ocr_processor.process_image(tmp_path, language=language)
            return jsonify({
                'success': True,
                'data': {
                    'file_name': f.filename,
                    'text': result.text,
                    'language': result.language or language,
                    'confidence': result.confidence,
                    'source': result.source or f.filename,
                }
            })
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    except Exception as e:
        logger.error(f"ocr_image 失败: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'OCR_FAILED', 'message': str(e)}
        }), 500


@document_api.route('/clean', methods=['POST'])
def clean_document():
    """
    文档清理（去页眉页脚/规范化空白）

    接受 JSON：{"text": "原始文本", "source": "可选来源标识"}
    """
    try:
        manager = get_unified_manager()
        if not manager.document_cleaner:
            return jsonify({
                'success': False,
                'error': {
                    'code': 'CLEANER_UNAVAILABLE',
                    'message': 'DocumentCleaner 未初始化'
                }
            }), 503

        body = request.get_json(silent=True) or {}
        text = body.get('text', '')
        source = body.get('source', 'inline')

        if not text:
            return jsonify({
                'success': False,
                'error': {'code': 'NO_TEXT', 'message': '缺少 text 字段'}
            }), 400

        result = manager.document_cleaner.clean_text(text, source=source)
        return jsonify({
            'success': True,
            'data': {
                'source': result.source,
                'original_length': len(result.original_text),
                'cleaned_length': len(result.cleaned_text),
                'removed_header': result.removed_header,
                'removed_footer': result.removed_footer,
                'removed_line_count': len(result.removed_lines or []),
                'cleaned_text': result.cleaned_text,
            }
        })

    except Exception as e:
        logger.error(f"clean_document 失败: {e}")
        return jsonify({
            'success': False,
            'error': {'code': 'CLEAN_FAILED', 'message': str(e)}
        }), 500


@document_api.route('/status', methods=['GET'])
def processor_status():
    """查询三个 T1 处理器状态"""
    manager = get_unified_manager()
    return jsonify({
        'success': True,
        'data': {
            'structured_processor': manager.structured_processor is not None,
            'ocr_processor': manager.ocr_processor is not None,
            'ocr_backend_available': (
                manager.ocr_processor._ocr_available
                if manager.ocr_processor else False
            ),
            'document_cleaner': manager.document_cleaner is not None,
        }
    })
