# -*- coding: utf-8 -*-
"""This module provides the ability to progamatically generate generic iTunes
style album artwork for various media types which were unable to find proper
iTunes album artwork
"""
from PIL import ImageFont, Image, ImageDraw, ImageOps

__author__ = 'Jon Nappi'

BLACK = 0, 0, 0
WHITE = 255, 255, 255


def _draw_text(text, path=None, size=60):
    """Return an image with *text* written to it, using either the specified
    *path* to a font file, or Courier New as the default.

    :param text: The text content to be drawn to the image
    :param path: The absolute path to a truetype font file
    :param size: font size
    """
    if path is None:
        path = '/Library/Fonts/Courier New.ttf'
    font = ImageFont.truetype(path, size)

    length = len(text) * 37
    text_box_dimensions = length, 80
    textbox = Image.new('L', text_box_dimensions)

    canvas = ImageDraw.Draw(text)
    canvas.text((0, 0), text, font=font, fill=255)
    return ImageOps.expand(textbox, border=10, fill=255)


def _build_background():
    """Return a canvas (ImageDraw.Draw, as it were) for the text to be drawn to
    """
    background_size = 600, 600
    background = Image.new('RGBA', background_size, WHITE)
    canvas = ImageDraw.Draw(background)
    return canvas


def _generate_text_offset(text_image, top=True):
    """Return positional tuples for artist and album text content image
    placement within the album artwork based on the length of the strings.
    It's unlikely that the length of *album* will ever vary much unless it's a
    show that has been around for a VERY (> 99 seasons) long time, so we don't
    bother to actually try and calculate anything for it
    """
    x = 600 - text_image.size[0]
    y = 180 if top else 340

    return int(x/2), y


def generate_artwork(artist, album, dest=None):
    """Generate an iTunes style album artowkr file with the contents of *album*
    written to it. Return the absolute path to the newly created album artwork
    file
    """
    if dest is None:
        dest = '.tmp.jpg'

    artist = _draw_text(artist)
    album = _draw_text(album)
    artwork = _build_background()

    # Place text onto background image
    artwork.paste(
        ImageOps.colorize(artist, WHITE, BLACK), _generate_text_offset(artist)
    )
    artwork.paste(
        ImageOps.colorize(album, WHITE, BLACK), _generate_text_offset(album,
                                                                      top=False)
    )

    artwork.save(dest)
    return dest
