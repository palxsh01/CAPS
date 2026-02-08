"""
Run Context Service

Helper script to start the FastAPI context service.
"""

import uvicorn
from caps.context.config import config


def main():
    """Start the context service."""
    print("=" * 60)
    print("  CAPS Context Service")
    print("  Starting FastAPI server...")
    print("=" * 60)
    print(f"\n🌐 Service will run at: http://{config.host}:{config.port}")
    print(f"📊 API docs available at: http://{config.host}:{config.port}/docs")
    print("\nPress Ctrl+C to stop\n")
    
    uvicorn.run(
        "caps.context.context_service:app",
        host=config.host,
        port=config.port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
