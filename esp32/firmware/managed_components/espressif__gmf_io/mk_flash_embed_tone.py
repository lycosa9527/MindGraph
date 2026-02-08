#!/user/bin/env python3

#  Espressif Modified MIT License
#
#  Copyright (c) 2025 Espressif Systems (Shanghai) CO., LTD
#
#  Permission is hereby granted for use EXCLUSIVELY with Espressif Systems products.
#  This includes the right to use, copy, modify, merge, publish, distribute, and sublicense
#  the Software, subject to the following conditions:
#
#  1. This Software MUST BE USED IN CONJUNCTION WITH ESPRESSIF SYSTEMS PRODUCTS.
#  2. The above copyright notice and this permission notice shall be included in all copies
#     or substantial portions of the Software.
#  3. Redistribution of the Software in source or binary form FOR USE WITH NON-ESPRESSIF PRODUCTS
#     is strictly prohibited.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED,
#  INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR
#  PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE
#  FOR ANY CLAIM, DAMAGES, OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
#  OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
#  DEALINGS IN THE SOFTWARE.
#
#  SPDX-License-Identifier: LicenseRef-Espressif-Modified-MIT

import sys
import os
import time
import argparse
import logging
from typing import Dict, Tuple, List
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
LICENSE_STR = f'''/*
 * SPDX-FileCopyrightText: {datetime.now().year} Espressif Systems (Shanghai) CO LTD
 *
 * SPDX-License-Identifier: Unlicense OR CC0-1.0
 */

'''

GEN_HEAD_FILE_NAME = 'esp_embed_tone.h'
GEN_CMAKE_FILE_NAME = 'esp_embed_tone.cmake'
SUPPORTED_EXTENSIONS = ('.wav', '.mp3', '.aac', '.m4a')

def sanitize_filename(filename: str) -> str:
    # Replace invalid characters with underscore
    sanitized = filename.replace('-', '_').replace('.', '_').replace(' ', '_')
    # Ensure it starts with a letter
    if sanitized[0].isdigit():
        sanitized = 'tone_' + sanitized
    return sanitized

def get_file_info(path: str) -> Dict[str, int]:
    try:
        file_list = [x for x in os.listdir(path) if x.lower().endswith(SUPPORTED_EXTENSIONS)]
        file_list.sort()
        if not file_list:
            logger.warning(f'No supported audio files found in {path}')
            return {}

        file_info = {}
        for filename in file_list:
            try:
                size = os.path.getsize(os.path.join(path, filename))
                file_info[filename] = size
                logger.info(f'Found audio file: {filename} ({size} bytes)')
            except OSError as e:
                logger.error(f'Error getting size for {filename}: {e}')
                continue
        return file_info
    except OSError as e:
        logger.error(f'Error scanning directory {path}: {e}')
        return {}

def gen_h_file(file_info: Dict[str, int]) -> Tuple[str, str]:
    if not file_info:
        logger.error('No file information provided')
        return '', ''

    # Header file content
    h_file = [
        '#pragma once',
        '',
        '/**',
        ' * @brief Structure for embedding tone information',
        ' */',
        'typedef struct {',
        '    const uint8_t *address;  /*!< Pointer to the embedded tone data */',
        '    int           size;      /*!< Size of the tone data in bytes */',
        '} esp_embed_tone_t;',
        ''
    ]
    # CMake file content
    cmake_file = ['set(COMPONENT_EMBED_TXTFILES']
    # Generate content for each file
    enum_entries = []
    url_entries = []
    tone_entries = []
    for idx, (filename, size) in enumerate(file_info.items()):
        sanitized = sanitize_filename(filename)
        # Add external reference
        h_file.extend([
            '/**',
            f' * @brief External reference to embedded tone data: {filename}',
            ' */',
            f'extern const uint8_t {sanitized}[] asm("_binary_{sanitized}_start");',
            ''
        ])
        # Add to CMake file
        cmake_file.append(f' {filename}')
        # Add tone entry
        tone_entries.append(
            f'    [{idx}] = {{\n'
            f'        .address = {sanitized},\n'
            f'        .size    = {size},\n'
            f'    }},'
        )
        # Add enum entry
        enum_entries.append(
            f'    ESP_EMBED_TONE_{sanitized.upper()} = {idx},'
        )
        # Add URL entry with hyphens replaced by underscores
        url_filename = filename.replace('-', '_')
        url_entries.append(
            f'    "embed://tone/{idx}_{url_filename}",'
        )
    # Complete header file
    h_file.extend([
        '/**',
        ' * @brief Array of embedded tone information',
        ' */',
        'esp_embed_tone_t g_esp_embed_tone[] = {',
        *tone_entries,
        '};',
        '',
        '/**',
        ' * @brief Enumeration for tone URLs',
        ' */',
        'enum esp_embed_tone_index {',
        *enum_entries,
        f'    ESP_EMBED_TONE_URL_MAX = {len(file_info)}',
        '};',
        '',
        '/**',
        ' * @brief Array of tone URLs',
        ' */',
        'const char * esp_embed_tone_url[] = {',
        *url_entries,
        '};',
        ''
    ])
    # Complete CMake file
    cmake_file.append(')')
    return '\n'.join(h_file), ''.join(cmake_file)

def write_file(content: str, filepath: str, is_header: bool = False) -> bool:
    try:
        if os.path.exists(filepath):
            os.remove(filepath)
        with open(filepath, 'w+') as f:
            if is_header:
                f.write(LICENSE_STR)
            f.write(content)
        logger.info(f'Successfully wrote {filepath}')
        return True
    except OSError as e:
        logger.error(f'Error writing to {filepath}: {e}')
        return False

def main():
    parser = argparse.ArgumentParser(
        description='Generate embedded audio tone header and CMake files',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        '-p', '--path',
        type=str,
        required=True,
        help='Base folder containing audio files'
    )
    parser.add_argument(
        '-v', '--verbose',
        action='store_true',
        help='Enable verbose output'
    )
    args = parser.parse_args()
    if args.verbose:
        logger.setLevel(logging.DEBUG)
    # Get file information
    file_info = get_file_info(args.path)
    if not file_info:
        logger.error('No valid audio files found')
        sys.exit(1)
    # Generate files
    h_content, cmake_content = gen_h_file(file_info)
    # Write files
    h_path = os.path.join(args.path, GEN_HEAD_FILE_NAME)
    cmake_path = os.path.join(args.path, GEN_CMAKE_FILE_NAME)
    if not write_file(h_content, h_path, is_header=True):
        sys.exit(1)
    if not write_file(cmake_content, cmake_path):
        sys.exit(1)
    logger.info('Successfully generated embedded tone files')

if __name__ == '__main__':
    main()
