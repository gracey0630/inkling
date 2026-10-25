from streamlit.testing.v1 import AppTest


def test_app_renders_and_labels_data_source():
    at = AppTest.from_file("../app/streamlit_app.py").run()
    assert not at.exception
    assert any("data: synthetic" in m.value for m in at.markdown)
