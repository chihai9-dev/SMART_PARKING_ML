"""OpenAPI document for the Flask ALPR service."""

OPENAPI_SPEC = {
    "openapi": "3.0.3",
    "info": {
        "title": "SmartParking Python AI Service",
        "version": "1.0.0",
        "description": (
            "API nhận diện biển số, phân loại màu nền và phục vụ ảnh scan. "
            "Tải ảnh bằng multipart/form-data với trường `image`."
        ),
    },
    "servers": [{"url": "http://localhost:5000"}],
    "tags": [
        {"name": "Nhận diện", "description": "Nhận diện biển số từ ảnh"},
        {"name": "Phân loại màu", "description": "Phân loại màu nền biển số"},
        {"name": "Mô hình", "description": "Thông tin mô hình màu"},
        {"name": "Lịch sử", "description": "Lịch sử scan tạm và ảnh kết quả"},
    ],
    "paths": {
        "/api/preview-plate": {
            "post": {
                "tags": ["Nhận diện"],
                "summary": "Nhận diện thử ảnh, không lưu lượt scan",
                "operationId": "previewPlate",
                "requestBody": {"$ref": "#/components/requestBodies/ImageUpload"},
                "responses": {
                    "200": {
                        "description": "Kết quả OCR và phân loại màu",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlatePreview"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            }
        },
        "/api/scan-plate": {
            "post": {
                "tags": ["Nhận diện"],
                "summary": "Nhận diện ảnh và lưu lượt scan",
                "description": (
                    "Phân tích ảnh, lưu ảnh scan trên Python service và thử gửi "
                    "bản ghi sang .NET API. Xem `database_saved` để biết trạng "
                    "thái lưu SQL Server."
                ),
                "operationId": "scanPlate",
                "requestBody": {"$ref": "#/components/requestBodies/ImageUpload"},
                "responses": {
                    "200": {
                        "description": "Kết quả nhận diện và trạng thái lưu",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ScanResult"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                    "503": {
                        "description": "Không kết nối được Backend nghiệp vụ",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/ApiError"}
                            }
                        },
                    },
                },
            }
        },
        "/api/classify-plate-color": {
            "post": {
                "tags": ["Phân loại màu"],
                "summary": "Phân loại màu từ ảnh crop biển số",
                "operationId": "classifyPlateColor",
                "requestBody": {"$ref": "#/components/requestBodies/ImageUpload"},
                "responses": {
                    "200": {
                        "description": "Dự đoán màu từ Random Forest và KNN",
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/PlateColor"}
                            }
                        },
                    },
                    "400": {"$ref": "#/components/responses/BadRequest"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            }
        },
        "/api/model-info": {
            "get": {
                "tags": ["Mô hình"],
                "summary": "Lấy metadata và báo cáo mô hình màu",
                "operationId": "getModelInfo",
                "responses": {
                    "200": {
                        "description": "Metadata mô hình",
                        "content": {"application/json": {"schema": {"type": "object"}}},
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                    "500": {"$ref": "#/components/responses/ServerError"},
                },
            }
        },
        "/api/scans": {
            "get": {
                "tags": ["Lịch sử"],
                "summary": "Lấy lịch sử scan tạm trong bộ nhớ",
                "operationId": "getScans",
                "responses": {
                    "200": {
                        "description": "Danh sách tối đa 100 lượt scan gần nhất",
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "status": {"type": "string", "example": "success"},
                                        "scans": {
                                            "type": "array",
                                            "items": {"type": "object"},
                                        },
                                    },
                                }
                            }
                        },
                    }
                },
            }
        },
        "/scan-image/{filename}": {
            "get": {
                "tags": ["Lịch sử"],
                "summary": "Xem hoặc tải ảnh scan",
                "operationId": "getScanImage",
                "parameters": [
                    {
                        "name": "filename",
                        "in": "path",
                        "required": True,
                        "description": "Tên file ảnh đã được lưu bởi dịch vụ AI",
                        "schema": {"type": "string"},
                    }
                ],
                "responses": {
                    "200": {
                        "description": "Nội dung ảnh",
                        "content": {
                            "image/jpeg": {"schema": {"type": "string", "format": "binary"}},
                            "image/png": {"schema": {"type": "string", "format": "binary"}},
                            "image/webp": {"schema": {"type": "string", "format": "binary"}},
                        },
                    },
                    "404": {"$ref": "#/components/responses/NotFound"},
                },
            }
        },
    },
    "components": {
        "requestBodies": {
            "ImageUpload": {
                "required": True,
                "content": {
                    "multipart/form-data": {
                        "schema": {
                            "type": "object",
                            "required": ["image"],
                            "properties": {
                                "image": {
                                    "type": "string",
                                    "format": "binary",
                                    "description": "Ảnh đầu vào, tối đa 8 MB",
                                }
                            },
                        }
                    }
                },
            }
        },
        "schemas": {
            "ApiError": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "example": "error"},
                    "message": {"type": "string"},
                },
            },
            "PlateColor": {
                "allOf": [
                    {"$ref": "#/components/schemas/ApiError"},
                    {
                        "type": "object",
                        "properties": {
                            "color_code": {"type": "string", "enum": ["White", "Yellow", "Unknown"]},
                            "color_label": {"type": "string"},
                            "confidence": {"type": "number", "format": "float"},
                            "probabilities": {
                                "type": "object",
                                "additionalProperties": {"type": "number"},
                            },
                            "algorithm": {"type": "string"},
                            "comparison": {"$ref": "#/components/schemas/PlateColor"},
                        },
                    },
                ]
            },
            "PlatePreview": {
                "type": "object",
                "properties": {
                    "status": {"type": "string"},
                    "plate": {"type": "string", "nullable": True},
                    "valid": {"type": "boolean"},
                    "confidence": {"type": "number", "format": "float"},
                    "engine": {"type": "string"},
                    "message": {"type": "string"},
                    "plate_color": {"$ref": "#/components/schemas/PlateColor"},
                    "bbox": {"type": "array", "items": {"type": "number"}},
                    "crop_jpeg_b64": {"type": "string", "format": "byte"},
                    "annotated_jpeg_b64": {"type": "string", "format": "byte"},
                },
            },
            "ScanResult": {
                "allOf": [
                    {"$ref": "#/components/schemas/PlatePreview"},
                    {
                        "type": "object",
                        "properties": {
                            "database_saved": {"type": "boolean"},
                            "database_message": {"type": "string", "nullable": True},
                            "image_path": {"type": "string"},
                            "crop_path": {"type": "string"},
                            "algorithm_comparison": {"type": "object", "nullable": True},
                        },
                    },
                ]
            },
        },
        "responses": {
            "BadRequest": {
                "description": "Ảnh thiếu, rỗng hoặc không giải mã được",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiError"}
                    }
                },
            },
            "NotFound": {
                "description": "Không tìm thấy metadata hoặc ảnh yêu cầu",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiError"}
                    }
                },
            },
            "ServerError": {
                "description": "Lỗi xử lý tại Python AI service",
                "content": {
                    "application/json": {
                        "schema": {"$ref": "#/components/schemas/ApiError"}
                    }
                },
            },
        },
    },
}
