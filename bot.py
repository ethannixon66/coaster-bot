from discord import (
    ApplicationContext,
    option,
    Embed,
    Intents
)
from discord.ext import commands, pages
from time import perf_counter
from coaster import Coaster
from rcdb import TooManyResultsError, get_coasters
from requests import Timeout
from toomanyresults import TooManyResultsError
import logging


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

intents = Intents.default()

bot = commands.Bot(command_prefix='$', intents=intents)

@bot.event
async def on_ready():
    logger.info(f'We have logged in as {bot.user}')


@bot.slash_command(
    description='Retrieves stats about the ride specified. Multiple pages may be returned if >1 matches are found'
)
@option('name', description='Name of the ride you want info for')
@option('park', description='Name of the park the ride is in (works best if spelled exactly)')
async def coaster(ctx: ApplicationContext, name, park=None):
    embeds = []
    coasters = []
    error_message = "Sorry, nothing was found :("
    await ctx.defer()
    try:
        start = perf_counter()
        coasters = [c for c in get_coasters(name, park) if c]
        end = perf_counter()
        logger.info(f"It took {end-start} seconds to get all coaster info")
    except Timeout:
        error_message = 'Connection timed out :('
    except TooManyResultsError:
        error_message = 'Sorry, your query was too vague'

    embeds = []
    for coaster in coasters:
        try:
            embeds.extend(build_embeds(coaster))
        except Exception:
            logger.exception(f"{coaster} was not real")

    if embeds:
        paginator = pages.Paginator(pages=embeds)
        await paginator.respond(ctx.interaction, ephemeral=False)
    else:
        await ctx.followup.send(error_message)


def build_embeds(coaster: Coaster) -> list[Embed]:
    embeds = []
    for track in coaster.tracks:
        if len(coaster.tracks) > 1:
            title = f'{coaster.name} ({track.name})'
        else:
            title = coaster.name

        embed = Embed(title=title, description=f'at {coaster.park}',
                      color=0xf55f5f, url=f'https://rcdb.com/{coaster._id}.htm')

        if coaster.country:
            embed.add_field(name='Country', value=coaster.country, inline=False)
        if coaster.opening_date:
            embed.add_field(name='Opening Date', value=coaster.opening_date, inline=True)
        if coaster.sbno_date:
            embed.add_field(name='SBNO Since', value=coaster.sbno_date, inline=True)
        if coaster.closing_date:
            embed.add_field(name='Closing Date', value=coaster.closing_date, inline=True)
        if coaster.manufacturer:
            embed.add_field(name='Manufacturer', value=coaster.manufacturer, inline=False)

        if track.height:
            embed.add_field(name='Height (ft)', value=track.height, inline=True)
        if track.drop:
            embed.add_field(name='Drop (ft)', value=track.drop, inline=True)
        if track.speed:
            embed.add_field(name='Speed (mph)', value=track.speed, inline=False)
        if track.length:
            embed.add_field(name='Length (ft)', value=track.length, inline=False)
        if track.inversions:
            embed.add_field(name='Inversions', value=track.inversions, inline=False)

        embed.set_footer(text='All images and information from rcdb.com')

        if coaster.image_url:
            embed.set_image(url=coaster.image_url)

        embeds.append(embed)
    return embeds
