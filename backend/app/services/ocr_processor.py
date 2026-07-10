import os
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class OCRResult:
    """OCR结果类"""
    text: str
    confidence: Optional[float] = None
    language: Optional[str] = None
    bounding_boxes: Optional[List[Dict[str, Any]]] = None
    source: str = ""


class OCRProcessor:
    """OCR处理器：识别图片中的文字"""

    def __init__(self):
        self._ocr_available = self._check_ocr_availability()

    def _check_ocr_availability(self) -> bool:
        """
        检查OCR库是否可用
        
        Returns:
            是否有可用的OCR库
        """
        # 尝试检查常用的OCR库
        ocr_libraries = ['pytesseract', 'easyocr', 'paddleocr']
        for lib in ocr_libraries:
            try:
                __import__(lib)
                return True
            except ImportError:
                continue
        return False

    def process_image(self, image_path: str, language: str = 'chi_sim+eng') -> OCRResult:
        """
        处理图片进行OCR识别
        
        Args:
            image_path: 图片文件路径
            language: 语言代码（如 'chi_sim+eng' 表示简体中文+英文）
            
        Returns:
            OCRResult对象
        """
        if not os.path.exists(image_path):
            return OCRResult(
                text="",
                source=image_path,
                confidence=0.0
            )

        # 尝试多种OCR方法
        methods = [
            self._process_with_pytesseract,
            self._process_with_easyocr,
            self._process_with_paddleocr
        ]

        for method in methods:
            try:
                result = method(image_path, language)
                if result and result.text.strip():
                    return result
            except Exception as e:
                print(f"{method.__name__} 处理失败: {str(e)}")
                continue

        # 如果所有方法都失败，返回空结果
        return OCRResult(
            text="",
            source=image_path,
            confidence=0.0,
            language=language
        )

    def _process_with_pytesseract(self, image_path: str, language: str) -> Optional[OCRResult]:
        """
        使用Tesseract OCR处理
        
        Args:
            image_path: 图片文件路径
            language: 语言代码
            
        Returns:
            OCRResult对象或None
        """
        try:
            import pytesseract
            from PIL import Image

            image = Image.open(image_path)

            # 转换语言代码为Tesseract格式
            tesseract_lang = language.replace('chi_sim', 'chi_sim').replace('+', '+')

            # 提取文本
            text = pytesseract.image_to_string(image, lang=tesseract_lang)

            # 获取详细数据（包括置信度）
            data = pytesseract.image_to_data(image, lang=tesseract_lang, output_type='dict')
            confidence = self._calculate_average_confidence(data)

            return OCRResult(
                text=text.strip(),
                confidence=confidence,
                language=language,
                source=image_path
            )
        except ImportError:
            return None
        except Exception:
            return None

    def _process_with_easyocr(self, image_path: str, language: str) -> Optional[OCRResult]:
        """
        使用EasyOCR处理
        
        Args:
            image_path: 图片文件路径
            language: 语言代码
            
        Returns:
            OCRResult对象或None
        """
        try:
            import easyocr

            # 转换语言代码为EasyOCR格式
            langs = []
            if 'chi_sim' in language:
                langs.append('ch_sim')
            if 'eng' in language:
                langs.append('en')
            if not langs:
                langs = ['ch_sim', 'en']

            reader = easyocr.Reader(langs)
            results = reader.readtext(image_path)

            text_parts = []
            bounding_boxes = []
            confidences = []

            for bbox, text, confidence in results:
                text_parts.append(text)
                confidences.append(confidence)
                bounding_boxes.append({
                    'bbox': bbox,
                    'text': text,
                    'confidence': confidence
                })

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text='\n'.join(text_parts),
                confidence=avg_confidence,
                language=language,
                bounding_boxes=bounding_boxes,
                source=image_path
            )
        except ImportError:
            return None
        except Exception:
            return None

    def _process_with_paddleocr(self, image_path: str, language: str) -> Optional[OCRResult]:
        """
        使用PaddleOCR处理
        
        Args:
            image_path: 图片文件路径
            language: 语言代码
            
        Returns:
            OCRResult对象或None
        """
        try:
            from paddleocr import PaddleOCR

            # 转换语言代码
            lang = 'ch' if 'chi_sim' in language else 'en'

            ocr = PaddleOCR(use_angle_cls=True, lang=lang, show_log=False)
            result = ocr.ocr(image_path, cls=True)

            text_parts = []
            bounding_boxes = []
            confidences = []

            if result and result[0]:
                for line in result[0]:
                    if line:
                        bbox, (text, confidence) = line
                        text_parts.append(text)
                        confidences.append(confidence)
                        bounding_boxes.append({
                            'bbox': bbox,
                            'text': text,
                            'confidence': confidence
                        })

            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                text='\n'.join(text_parts),
                confidence=avg_confidence,
                language=language,
                bounding_boxes=bounding_boxes,
                source=image_path
            )
        except ImportError:
            return None
        except Exception:
            return None

    def _calculate_average_confidence(self, data: Dict[str, Any]) -> float:
        """
        计算平均置信度
        
        Args:
            data: OCR数据字典
            
        Returns:
            平均置信度
        """
        try:
            confidences = [conf for conf in data.get('conf', []) if conf > 0]
            if confidences:
                return sum(confidences) / len(confidences) / 100.0
        except Exception:
            pass
        return 0.0

    def process_images_batch(self, image_paths: List[str], language: str = 'chi_sim+eng') -> Dict[str, OCRResult]:
        """
        批量处理图片
        
        Args:
            image_paths: 图片文件路径列表
            language: 语言代码
            
        Returns:
            图片路径到OCRResult的字典映射
        """
        results = {}
        for image_path in image_paths:
            results[image_path] = self.process_image(image_path, language)
        return results

    def process_pdf_images(self, pdf_path: str, language: str = 'chi_sim+eng') -> List[OCRResult]:
        """
        从PDF中提取图片并进行OCR识别
        
        Args:
            pdf_path: PDF文件路径
            language: 语言代码
            
        Returns:
            OCRResult列表
        """
        try:
            from pypdf import PdfReader
            import tempfile

            results = []
            reader = PdfReader(pdf_path)

            for page_num, page in enumerate(reader.pages):
                if '/Resources' in page and '/XObject' in page['/Resources']:
                    xObject = page['/Resources']['/XObject'].get_object()

                    for obj in xObject:
                        if xObject[obj]['/Subtype'] == '/Image':
                            try:
                                # 提取图片数据
                                image_data = xObject[obj]._data
                                
                                # 创建临时文件
                                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as temp_file:
                                    temp_file.write(image_data)
                                    temp_path = temp_file.name

                                # 处理图片
                                ocr_result = self.process_image(temp_path, language)
                                ocr_result.source = f"{pdf_path} (page {page_num + 1})"
                                results.append(ocr_result)

                                # 清理临时文件
                                os.unlink(temp_path)
                            except Exception as e:
                                print(f"处理PDF图片失败: {str(e)}")
                                continue

            return results
        except Exception as e:
            print(f"PDF图片OCR处理失败: {str(e)}")
            return []

    def get_available_languages(self) -> List[str]:
        """
        获取可用的语言列表
        
        Returns:
            语言代码列表
        """
        return [
            'chi_sim',  # 简体中文
            'chi_tra',  # 繁体中文
            'eng',      # 英文
            'jpn',      # 日文
            'kor',      # 韩文
            'chi_sim+eng',  # 简体中文+英文
        ]

    def is_available(self) -> bool:
        """
        检查OCR功能是否可用
        
        Returns:
            是否可用
        """
        return self._ocr_available
