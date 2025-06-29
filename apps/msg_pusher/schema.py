# Use HTTP POST requests to `http://localhost:8011/push` with the following schema defined JSON payloads to send messages to Discord users via Cecilia bot.

MESSAGE_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Discord Message Push Schema",
    "description": "Schema for pushing messages to Discord users via Cecilia bot",
    "type": "object",
    "required": ["user_id", "message"],
    "properties": {
        "user_id": {
            "type": "string",
            "pattern": "^[0-9]{17,19}$",
            "description": "Discord user ID (17-19 digits)"
        },
        "message": {
            "type": "object",
            "description": "Message content object",
            "properties": {
                "content": {
                    "type": "string",
                    "maxLength": 2000,
                    "description": "Plain text message content (max 2000 characters)"
                },
                "embed": {
                    "type": "object",
                    "description": "Rich embed object",
                    "properties": {
                        "title": {
                            "type": "string",
                            "maxLength": 256,
                            "description": "Embed title"
                        },
                        "description": {
                            "type": "string",
                            "maxLength": 4096,
                            "description": "Embed description"
                        },
                        "color": {
                            "type": "string",
                            "pattern": "^#[0-9A-Fa-f]{6}$",
                            "description": "Hex color code (e.g., #FF5733)"
                        },
                        "fields": {
                            "type": "array",
                            "maxItems": 25,
                            "description": "Array of embed fields",
                            "items": {
                                "type": "object",
                                "required": ["name", "value"],
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "maxLength": 256,
                                        "description": "Field name"
                                    },
                                    "value": {
                                        "type": "string",
                                        "maxLength": 1024,
                                        "description": "Field value"
                                    },
                                    "inline": {
                                        "type": "boolean",
                                        "default": false,
                                        "description": "Whether field should be inline"
                                    }
                                }
                            }
                        },
                        "footer": {
                            "type": "object",
                            "required": ["text"],
                            "properties": {
                                "text": {
                                    "type": "string",
                                    "maxLength": 2048,
                                    "description": "Footer text"
                                }
                            }
                        }
                    }
                },
                "components": {
                    "type": "array",
                    "maxItems": 5,
                    "description": "Interactive components",
                    "items": {
                        "type": "object",
                        "required": ["type", "label"],
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["button"],
                                "description": "Component type"
                            },
                            "label": {
                                "type": "string",
                                "maxLength": 80,
                                "description": "Button label"
                            },
                            "url": {
                                "type": "string",
                                "format": "uri",
                                "description": "URL for link buttons"
                            }
                        }
                    }
                }
            },
            "anyOf": [
                {"required": ["content"]},
                {"required": ["embed"]},
                {"required": ["components"]}
            ]
        },
        "channel_id": {
            "type": "string",
            "pattern": "^[0-9]{17,19}$",
            "description": "Optional channel ID (if not provided, sends as DM)"
        },
        "priority": {
            "type": "string",
            "enum": ["low", "normal", "high", "urgent"],
            "default": "normal",
            "description": "Message priority level"
        },
        "timestamp": {
            "type": "string",
            "format": "date-time",
            "description": "ISO 8601 timestamp when message was created"
        }
    }
}

# Example messages for documentation
EXAMPLE_MESSAGES = {
    "simple_text": {
        "user_id": "123456789012345678",
        "message": {
            "content": "Hello! Your essay summary is ready."
        }
    },
    "rich_embed": {
        "user_id": "123456789012345678",
        "message": {
            "embed": {
                "title": "📚 New Research Papers",
                "description": "Found 5 new papers on Machine Learning",
                "color": "#00FF00",
                "fields": [
                    {
                        "name": "Topic",
                        "value": "Machine Learning",
                        "inline": True
                    },
                    {
                        "name": "Count",
                        "value": "5 papers",
                        "inline": True
                    }
                ],
                "footer": {
                    "text": "Powered by ArXiv API"
                }
            }
        },
        "priority": "normal"
    },
    "with_button": {
        "user_id": "123456789012345678",
        "message": {
            "content": "Check out this research paper!",
            "components": [
                {
                    "type": "button",
                    "label": "Read Paper",
                    "url": "https://arxiv.org/abs/2024.00001"
                }
            ]
        }
    }
}
