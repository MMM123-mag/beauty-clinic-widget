"""
Deploy script for Beauty Clinic booking widget.
1. Updates Proxy workflow (adds booking methods)
2. Deploys widget HTML to hosting workflow
"""
import json
import urllib.request
import sys
import os

N8N_BASE = 'https://markins.app.n8n.cloud/api/v1'
N8N_API_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJmM2EwYWMxMS02NzgzLTQxZDEtYWE2Ni03ZDgzYzRiNDE5NGQiLCJpc3MiOiJuOG4iLCJhdWQiOiJwdWJsaWMtYXBpIiwianRpIjoiODc1ZmUyYzQtN2Q5YS00NDBiLTkwYzYtYjNiM2I4Y2FmODcxIiwiaWF0IjoxNzc0MTk2MzAwfQ.YpsBA8hBMChVSql_kMnakYhic_sNAIytqkeJ7ktUMF0'

PROXY_WORKFLOW_ID = 'MrDYkL8iofWaJebc'
WIDGET_WORKFLOW_ID = 'c45lEmvbJJaYAulD'

def n8n_request(method, path, data=None):
    url = N8N_BASE + path
    body = json.dumps(data).encode('utf-8') if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header('X-N8N-API-KEY', N8N_API_KEY)
    req.add_header('Content-Type', 'application/json')
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        error_body = e.read().decode('utf-8')
        print(f'HTTP {e.code}: {error_body}')
        sys.exit(1)

# ============================================================
# STEP 1: Update Proxy workflow — add booking methods
# ============================================================
def update_proxy():
    print('=== Step 1: Updating Proxy workflow ===')

    # Get current workflow
    wf = n8n_request('GET', f'/workflows/{PROXY_WORKFLOW_ID}')

    # Find the Process (Code) node
    code_node = None
    for node in wf['nodes']:
        if node['name'] == 'Process':
            code_node = node
            break

    if not code_node:
        print('ERROR: Process node not found in proxy workflow')
        sys.exit(1)

    old_code = code_node['parameters']['jsCode']

    # Check if already updated
    if 'book_dates' in old_code:
        print('Proxy already has booking methods, skipping update.')
        return

    # Add new cases before the default case in handleYclients
    new_cases = """    case 'book_dates': {
      url = `https://api.yclients.com/api/v1/book_dates/${companyId}`;
      const bdQs = [];
      if (params.staff_id) bdQs.push('staff_id=' + params.staff_id);
      if (params.service_ids) params.service_ids.forEach(id => bdQs.push('service_ids[]=' + id));
      if (bdQs.length) url += '?' + bdQs.join('&');
      break;
    }
    case 'book_times': {
      url = `https://api.yclients.com/api/v1/book_times/${companyId}/${params.staff_id}/${params.date}`;
      const btQs = (params.service_ids || []).map(id => 'service_ids[]=' + id);
      if (btQs.length) url += '?' + btQs.join('&');
      break;
    }
    case 'records.create': {
      url = `https://api.yclients.com/api/v1/records/${companyId}`;
      httpMethod = 'POST';
      reqBody = params.body;
      break;
    }
    case 'client.create': {
      url = `https://api.yclients.com/api/v1/client/${companyId}`;
      httpMethod = 'POST';
      reqBody = { name: params.name, phone: params.phone };
      if (params.email) reqBody.email = params.email;
      break;
    }
"""

    # Insert before the default case
    default_marker = "    default:\n      return { status: 'error', error: `Неизвестный метод YCLIENTS:"
    if default_marker not in old_code:
        # Try alternative marker
        default_marker = "    default:"

    new_code = old_code.replace(default_marker, new_cases + '    ' + default_marker.lstrip())

    # Also update staff.list to accept service_ids
    old_staff = "    case 'staff.list':\n      url = `https://api.yclients.com/api/v1/company/${companyId}/staff`;\n      break;"
    new_staff = """    case 'staff.list': {
      url = `https://api.yclients.com/api/v1/company/${companyId}/staff`;
      if (params.service_ids && params.service_ids.length) {
        url += '?' + params.service_ids.map(id => 'service_ids[]=' + id).join('&');
      }
      break;
    }"""
    new_code = new_code.replace(old_staff, new_staff)

    # Update the describe methods list to include new methods
    old_methods_list = "'storage.list', 'goods.list', 'categories.list'"
    new_methods_list = "'storage.list', 'goods.list', 'categories.list', 'book_dates', 'book_times', 'records.create', 'client.create'"
    new_code = new_code.replace(old_methods_list, new_methods_list)

    # Update the error message with available methods
    old_error_methods = "company.info, services.list, staff.list, records.list, clients.list, client.get, schedule.list, finances.transactions, storage.list, goods.list, categories.list"
    new_error_methods = "company.info, services.list, staff.list, records.list, clients.list, client.get, schedule.list, finances.transactions, storage.list, goods.list, categories.list, book_dates, book_times, records.create, client.create"
    new_code = new_code.replace(old_error_methods, new_error_methods)

    code_node['parameters']['jsCode'] = new_code

    # PUT updated workflow (settings must be minimal)
    allowed_settings = ['executionOrder', 'callerPolicy']
    clean_settings = {k: v for k, v in wf.get('settings', {}).items() if k in allowed_settings}
    payload = {
        'name': wf['name'],
        'nodes': wf['nodes'],
        'connections': wf['connections'],
        'settings': clean_settings
    }

    result = n8n_request('PUT', f'/workflows/{PROXY_WORKFLOW_ID}', payload)
    print(f'Proxy updated successfully. Version: {result.get("versionId", "?")}')


# ============================================================
# STEP 2: Deploy widget HTML to hosting workflow
# ============================================================
def deploy_widget():
    print('=== Step 2: Deploying widget HTML ===')

    # Read HTML file
    html_path = os.path.join(os.path.dirname(__file__), 'booking.html')
    with open(html_path, 'r', encoding='utf-8') as f:
        html_content = f.read()

    # Build workflow with: Webhook (GET) → Code (return HTML) → Respond to Webhook (text/html)
    # Using Code node to return HTML as it handles large content better

    # Escape backticks and ${} in HTML for JS template literal
    html_escaped = html_content.replace('\\', '\\\\').replace('`', '\\`').replace('${', '\\${')

    js_code = 'const html = `' + html_escaped + '`;\nreturn { json: { html } };'

    workflow_payload = {
        'name': 'Beauty Clinic — Виджет записи',
        'nodes': [
            {
                'parameters': {
                    'path': '8f15a745-732b-437e-a447-814e46f0f4b1',
                    'responseMode': 'responseNode',
                    'options': {}
                },
                'type': 'n8n-nodes-base.webhook',
                'typeVersion': 2,
                'position': [0, 0],
                'id': '5b3710ca-5998-4d8c-b208-15a2113422a2',
                'name': 'Webhook',
                'webhookId': '8f15a745-732b-437e-a447-814e46f0f4b1'
            },
            {
                'parameters': {
                    'jsCode': js_code
                },
                'type': 'n8n-nodes-base.code',
                'typeVersion': 2,
                'position': [300, 0],
                'id': 'code-html-node',
                'name': 'HTML Content'
            },
            {
                'parameters': {
                    'respondWith': 'text',
                    'responseBody': '={{ $json.html }}',
                    'options': {
                        'responseHeaders': {
                            'entries': [
                                {
                                    'name': 'Content-Type',
                                    'value': 'text/html; charset=utf-8'
                                }
                            ]
                        }
                    }
                },
                'type': 'n8n-nodes-base.respondToWebhook',
                'typeVersion': 1.1,
                'position': [600, 0],
                'id': 'respond-html-node',
                'name': 'Respond HTML'
            }
        ],
        'connections': {
            'Webhook': {
                'main': [[{'node': 'HTML Content', 'type': 'main', 'index': 0}]]
            },
            'HTML Content': {
                'main': [[{'node': 'Respond HTML', 'type': 'main', 'index': 0}]]
            }
        },
        'settings': {}
    }

    result = n8n_request('PUT', f'/workflows/{WIDGET_WORKFLOW_ID}', workflow_payload)
    print(f'Widget deployed successfully. Version: {result.get("versionId", "?")}')
    print(f'Widget URL: https://markins.app.n8n.cloud/webhook/8f15a745-732b-437e-a447-814e46f0f4b1')


if __name__ == '__main__':
    update_proxy()
    print()
    deploy_widget()
    print()
    print('=== DONE ===')
    print('Next step: Register local app in Bitrix24 with this handler URL:')
    print('https://markins.app.n8n.cloud/webhook/8f15a745-732b-437e-a447-814e46f0f4b1')
