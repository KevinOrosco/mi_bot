import discord
import random
import asyncio
from discord.ext import commands
import os
from dotenv import load_dotenv


# Cargar token
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Intents necesarios para detectar miembros y mensajes
intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix='!', intents=intents)

partidas = {}  # Diccionario de partidas por servidor

@bot.event
async def on_ready():
    print(f'{bot.user} ha iniciado sesión')

@bot.command()
async def hola(ctx):
    await ctx.send(f'¡Hola {ctx.author.mention}! ¿Cómo estás? 👋')

# Requisitos para crear una partida
def crear_partida(ctx):
    partidas[ctx.guild.id] = {
        "jugadores": [ctx.author],
        "estado": "esperando",
        "creador": ctx.author,
        "canal": ctx.channel,
        "roles": {},
        "vivos": set(),
        "num_jugadores": None
    }

# Lógica para asignar roles basada en la cantidad de jugadores
def obtener_roles(jugadores):
    # Obtenemos la cantidad total de jugadores que se unieron a la partida
    num_jugadores = len(jugadores)

    # Asignamos la cantidad de mafiosos: al menos 1, y aproximadamente el 25% del total
    # Usamos // (división entera) para evitar decimales, y max para garantizar al menos 1 mafia
    mafiosos = max(1, num_jugadores // 4) 

    # La cantidad de doctores y detectives escala según el número de jugadores:
    # - 1 para hasta 6 jugadores
    # - 2 entre 7 y 12
    # - 3 para más de 13
    doctores = 1 if num_jugadores <= 6 else 2 if num_jugadores <= 12 else 3
    detectives = doctores # Usamos la misma cantidad de detectives que de doctores

    # Construimos la lista de roles:
    roles = (["mafia"] * mafiosos +  #Asignamos la cantidad de jugadores que seran mafia
    ["doctor"] * doctores +     #Asignamos la cantidad de jugadores que seran doctores
    ["detective"] * detectives +    #Asignamos la cantidad de jugadores que seran detectives
    ["ciudadano"] * (num_jugadores - mafiosos - doctores - detectives)) #A la cantidad total de jugadores, le restamos la cantidad total de roles especiales
                                                                        #el resultado sera la cantidad de ciudadanos.    
    # Mezclamos los roles de la lista al azar para que la asignación no sea predecible
    random.shuffle(roles)

    # Asignamos cada rol a un jugador usando zip y lo convertimos en un diccionario
    return dict(zip(jugadores, roles))

@bot.command() 
async def mafia(ctx, subcomando=None, num: int = None): # Comando principal del juego Mafia. Con subcomandos como 'crear', 'unirme', 'iniciar', 'cancelar', etc.
    
    # Subcomando para crear una nueva partida
    if subcomando == "crear":

        # Verificamos si ya existe una partida activa en este servidor
        if ctx.guild.id in partidas:
            await ctx.send("⚠️ Ya hay una partida en curso en este servidor.")
            return

        # Validamos que se haya indicado un número de jugadores válido (entre 4 y 30)
        if num is None or num < 4 or num > 30:
            await ctx.send("❌ Debes especificar un número de jugadores (mínimo 4, maximo 30). Ej: `!mafia crear 6`")
            return

        # Creamos la partida inicializando su estructura interna
        crear_partida(ctx)
        # Guardamos el número de jugadores especificado por el creador
        partidas[ctx.guild.id]["num_jugadores"] = num

        # Enviamos un mensaje informativo
        await ctx.send(
            f"🛠️ **¡Partida creada!** 🎮 Se jugará con **{num} jugadores**.\n"
            f"📢 Usa `!mafia unirme` para participar.\n"
            f"👤 **{ctx.author.display_name}** se ha unido. Faltan **{num - 1}** jugadores...\n"
            f"⚠️ En caso de no llenar la partida, el creador puede iniciarla manualmente con `!mafia iniciar` (solo para partidas de 5 o más).\n"
            f"⚠️ El creador puede cancelar la partida usando `!mafia cancelar`."
        )
    
    # Subcomando para que los jugadores se unan a una partida en curso
    elif subcomando == "unirme":
        # Obtenemos la partida del servidor actual
        partida = partidas.get(ctx.guild.id)

         # Verificamos que exista una partida y que esté en estado "esperando"
        if not partida or partida["estado"] != "esperando":
            await ctx.send("❌ No hay partida disponible para unirse.")
            return

         # Si el jugador ya se unió anteriormente, se lo informamos
        if ctx.author in partida["jugadores"]:
            await ctx.send("ℹ️ Ya estás en la partida.")
            return
         
          # Agregamos al jugador a la lista de participantes
        partida["jugadores"].append(ctx.author)
        
        # Calculamos cuántos jugadores faltan para completar la partida
        faltan = partida["num_jugadores"] - len(partida["jugadores"])

         
         # Si aún faltan jugadores, mostramos el progreso actual
        if faltan > 0:
            await ctx.send(f"✅ **{ctx.author.display_name}** se ha unido a la partida.\n👥 Jugadores actuales: **{len(partida['jugadores'])}/{partida['num_jugadores']}**\n⏳ Faltan **{faltan}** para comenzar...")
        
        # Si se completó la cantidad de jugadores, iniciamos la partida automáticamente
        else:
            
            await ctx.send("✅ **¡Estamos listos!** 🚀 Iniciando...")
             # Llamamos a la función que inicia la lógica principal del juego
            await iniciar_partida(ctx, partida)

    # Subcomando para que el creador inicie manualmente la partida, útil si no se llena pero hay suficientes jugadores
    elif subcomando == "iniciar":
        # Obtenemos la partida del servidor actual
        partida = partidas.get(ctx.guild.id)

        # Verificamos que haya una partida creada
        if not partida:
            await ctx.send("❌ No hay ninguna partida creada en este servidor.")
            return

        # Verificamos que la partida no haya sido ya iniciada
        if partida["estado"] != "esperando":
            await ctx.send("⚠️ La partida ya fue iniciada.")
            return

        # Solo el creador puede iniciar la partida manualmente
        if ctx.author != partida["creador"]:
            await ctx.send("🚫 Solo el creador de la partida puede iniciarla manualmente.")
            return
        # Validamos que haya al menos el mínimo de jugadores para que el juego tenga sentido (4 jugadores)
        if len(partida["jugadores"]) < 4:
            await ctx.send("🚫 Se necesitan al menos 4 jugadores para comenzar la partida.")
            return
        # Si todo está en orden, se inicia la partida manualmente
        await ctx.send("✅ **¡Estamos listos!** 🚀 Iniciando...")
        await iniciar_partida(ctx, partida)

    # Subcomando para cancelar una partida antes de que comience, útil si no se llenan los jugadores o hay cambios de planes
    elif subcomando == "cancelar":
        # Obtenemos la partida actual del servidor
        partida = partidas.get(ctx.guild.id)

        # Verificamos que haya una partida activa que se pueda cancelar
        if not partida:
            await ctx.send("❌ No hay ninguna partida activa para cancelar.")
            return

        # Solo el creador de la partida tiene permiso para cancelarla
        if ctx.author != partida.get("creador"):
            await ctx.send("🚫 Solo el creador de la partida puede cancelarla.")
            return
        
        # Eliminamos la partida del diccionario global para borrarla completamente
        del partidas[ctx.guild.id]
        # Avisamos que la partida fue cancelada correctamente
        await ctx.send("🛑 La partida ha sido cancelada por el creador.")

    #En caso de que el no haya comando(ejemplo: !mafia )
    elif subcomando is None:
        await ctx.send("🧩 Falta especificar un subcomando. Por ejemplo: `!mafia crear`")

    else:
        # Subcomando no reconocido
        await ctx.send(f"**{ctx.author.mention}**, vos queres que te coja, no? 🤨")

# Esta función gestiona todo el flujo del juego: asigna roles, controla las fases de noche y día, y verifica condiciones de victoria
async def iniciar_partida(ctx, partida):
    jugadores = partida["jugadores"]
    # Creamos un conjunto con los jugadores vivos al inicio
    partida["vivos"] = set(jugadores)
    # Asignamos roles de forma aleatoria y balanceada
    partida["roles"] = obtener_roles(jugadores)

    # Enviamos a cada jugador un mensaje privado con su rol
    for jugador in jugadores:
        try:
            await jugador.send(f"🎭 **¡Tu rol ha sido asignado!**\n🔒 Eres **{partida['roles'][jugador].upper()}**.\n🤫 ¡Guardá el secreto!")
        except:
            # Si no se puede mandar DM (por ejemplo, tiene bloqueado los mensajes del servidor)
            await ctx.send(f"⚠️ No se pudo enviar el rol a {jugador.display_name}.")

    # Obtenemos el canal original donde se creó la partida
    canal = partida["canal"]
    # Anunciamos públicamente el inicio del juego
    await canal.send("🎉 **¡La partida ha comenzado!** 🔥 Que comience la masacre...\n🌙 **Cae la noche...** Los roles especiales están actuando...")

bot.run(TOKEN) # Corremos el bot