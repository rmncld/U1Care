import struct
from pathlib import Path
import pytest
from homeassistant.loader import async_get_integration
from homeassistant.components.brands import _read_brand_file
from homeassistant.components.brands.const import ALLOWED_IMAGES


@pytest.mark.asyncio
async def test_local_brand_is_detected_and_serves_all_theme_variants(hass):
    integration = await async_get_integration(hass, 'u1_companion')
    assert integration.has_branding
    folder = Path(__file__).parents[1] / 'custom_components/u1_companion/brand'
    for image in ALLOWED_IMAGES:
        data = _read_brand_file(folder, image)
        assert data.startswith(b'\x89PNG\r\n\x1a\n')
        width, height = struct.unpack('>II', data[16:24])
        assert width == height and width in (256, 512)
    assert struct.unpack('>II', _read_brand_file(folder, 'icon@2x.png')[16:24]) == (512, 512)
