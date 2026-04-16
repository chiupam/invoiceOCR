class TestRoutes:

    def test_index_redirects_to_login(self, client):
        response = client.get('/')
        assert response.status_code == 302
        assert '/auth' in response.headers['Location']

    def test_upload_requires_login(self, client):
        response = client.get('/upload')
        assert response.status_code == 302
        assert '/auth' in response.headers['Location']

    def test_api_statistics_requires_login(self, client):
        response = client.get('/api/statistics')
        assert response.status_code == 302

    def test_project_list_requires_login(self, client):
        response = client.get('/projects')
        assert response.status_code == 302

    def test_settings_requires_login(self, client):
        response = client.get('/settings')
        assert response.status_code == 302

    def test_invoice_create_requires_login(self, client):
        response = client.get('/invoice/create')
        assert response.status_code == 302

    def test_static_assets_accessible(self, client):
        response = client.get('/static/css/style.css')
        assert response.status_code in (200, 304)
