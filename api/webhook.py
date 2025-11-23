from bot import handle_update
import json, asyncio

def handler(request):
    # Vercel sends raw body as bytes; request.body is string in this environment simulation
    if request.method != 'POST':
        return {'statusCode': 200, 'body': 'OK'}

    try:
        data = json.loads(request.body)
    except Exception:
        return {'statusCode': 400, 'body': 'bad request'}

    # Run aiogram update handler
    asyncio.run(handle_update(data))
    return {'statusCode': 200, 'body': 'OK'}
