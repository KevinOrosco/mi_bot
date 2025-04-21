#pipenv install -U discord.py
import discord
import random
import asyncio
from discord.ext import commands
from discord.ui import Button, View
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
        "acciones": {},
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

    #El bucle continuara hasta que se cierre con un break
    while True:
        # --------- FASE DE NOCHE ---------
        partida["estado"] = "noche"
        partida["acciones"] = {}  # Reiniciamos las acciones nocturnas

        # Anuncio general de que comenzó la noche
        await canal.send("----------🌕**NOCHE**🌕----------\n🌌 **NOCHE** ha caído sobre el pueblo...\n⏳ Aquellos con habilidades tienen **60 segundos** para actuar.⏳\n😴 Los ciudadanos... duermen sin sospechar.")

        vivos = list(partida["vivos"]) # Convertimos el set de vivos a lista

        # Enviamos botones de acción a mafia, doctor y detective
        for jugador in vivos:

            # Obtenemos el rol del jugador actual
            rol = partida["roles"][jugador]

            # Solo enviamos botones a los que tienen rol activo en la noche
            if rol in ["doctor", "detective", "mafia"]:
                # Creamos una vista (grupo de botones) con un timeout de 90 segundos
                view = View(timeout=90)
                # Por cada jugador vivo, generamos un botón como posible objetivo
                for objetivo in vivos:
                    
                    # Creamos un botón con el nombre del objetivo
                    button = Button(label=objetivo.display_name, style=discord.ButtonStyle.primary)
                    # Definimos lo que pasa cuando alguien clickea el botón
                    async def callback(interaction, obj=objetivo, jug=jugador, rol=rol):

                        # Si alguien distinto al dueño del botón intenta usarlo, se le niega
                        if interaction.user != jug:
                            await interaction.response.send_message("🚫 Este botón no es para vos.", ephemeral=True)
                            return

                        # Si el jugador ya eligió antes, no puede volver a elegir
                        if jug in partida["acciones"]:
                            await interaction.response.send_message("⚠️ Ya has elegido a tu objetivo.", ephemeral=True)
                            return

                        # Guardamos la acción del jugador: qué rol tiene y a quién apuntó
                        partida["acciones"][jug] = (rol, obj)

                        # Confirmamos al jugador su elección en un mensaje privado
                        await interaction.response.send_message(f"✅ Elegiste a **{obj.display_name}**.", ephemeral=True)
                       
                    # Asociamos el callback al botón
                    button.callback = callback
                    # Agregamos el botón a la vista
                    view.add_item(button)
                
                # Le enviamos al jugador por DM la vista con los botones para que elija
                try:
                    await jugador.send(f"🕹️ **¡Hora de actuar, {rol.upper()}!**\nElegí a quién usar tu habilidad:\n⬇️⬇️⬇️", view=view)
                # Si no se puede enviar (por DMs bloqueados, por ejemplo), avisamos en el canal
                except:
                    await canal.send(f"⚠️ No se pudo enviar opciones a {jugador.display_name}.")

        # Esperamos 60 segundos para que todos tengan tiempo de elegir
        await asyncio.sleep(60)

        # Recopilamos los objetivos elegidos por los mafiosos
        mafia_targets = [accion[1] for jug, accion in partida["acciones"].items() if accion[0] == "mafia"]
        # Seleccionamos aleatoriamente a una víctima de entre las elecciones de los mafiosos
        objetivo_mafia = random.choice(mafia_targets) if mafia_targets else None

        # Inicializamos la variable que almacenará a quién curó el doctor
        objetivo_curado = None

        # Recorremos todas las acciones realizadas durante la noche
        for jug, (accion, obj) in partida["acciones"].items():

            # Si el rol es doctor, guardamos a quién curó (puede haber varios doctores, pero el último sobrescribirá)
            if accion == "doctor":
                objetivo_curado = obj
        
        # Recorremos otra vez las acciones para procesar lo que hizo el detective
        for jug, (accion, obj) in partida["acciones"].items():
            if accion == "detective":

                # Obtenemos el rol de la persona investigada por el detective
                rol_obj = partida["roles"].get(obj)
                try:
                     # Enviamos por DM el resultado de la investigación
                    await jug.send(f"🔍 **Investigación completada**:\n🧑‍✈️ **{obj.display_name}** es... **{rol_obj.upper()}**.")
                except:
                    await canal.send(f"⚠️ No se pudo enviar el resultado al detective {jug.display_name}.")

        # Inicializamos la variable que almacenará a la víctima de la mafia
        muerto = None
        # Si la mafia eligió a alguien, y ese alguien no fue curado por el doctor, y sigue vivo...
        if objetivo_mafia and objetivo_mafia != objetivo_curado and objetivo_mafia in partida["vivos"]:
            # ...entonces esa persona muere (la removemos de la lista de vivos)
            partida["vivos"].remove(objetivo_mafia)
            muerto = objetivo_mafia # Y la guardamos como "muerto" para anunciarlo luego

        # Actualizamos el estado de la partida a "día" para iniciar la siguiente fase
        partida["estado"] = "dia"

        # Si hay un jugador muerto (es decir, la mafia mató a alguien que no fue curado)
        if muerto:
            # Anunciamos el inicio del día y el nombre del jugador asesinado
            await canal.send(f"----------☀️**DIA**☀️----------\n☀️ **¡Amanece un nuevo día!**\n💀 Durante la noche, **{muerto.display_name}** fue encontrado... sin vida.")
            # Obtenemos los roles de los jugadores que siguen vivos
            vivos_roles = [partida["roles"][j] for j in partida["vivos"]]
            mafias = vivos_roles.count("mafia") # Contamos cuántas mafias quedan vivas
            no_mafias = len(partida["vivos"]) - mafias # Calculamos cuántos no-mafias quedan

            # Condición de victoria: si no quedan mafias vivas, gana el pueblo
            if mafias == 0:
                await anunciar_fin(canal, partida, ganadores="Ciudadanos")
                break
            # Condición de victoria: si las mafias son igual o más que los no-mafias, gana la mafia
            elif mafias >= no_mafias:
                await anunciar_fin(canal, partida, ganadores="Mafia")
                break
        else:
            await canal.send("----------☀️**DIA**☀️----------\n☀️ **¡Amanece un nuevo día!**\n😮 Pero esta vez... **¡nadie murió!**\n🧐 ¿Una protección o un error de cálculo?")

        await canal.send("🗳️ **Es hora de votar**: ¿quién creés que es parte de la mafia?")

        # Diccionario para guardar los votos realizados
        votos = {}
        # Creamos una vista con botones para que los jugadores voten
        view = View()

        # Por cada jugador vivo, agregamos un botón para votar por él
        for objetivo in partida["vivos"]:
            button = Button(label=objetivo.display_name, style=discord.ButtonStyle.danger)

            # Función que se ejecuta cuando se hace clic en un botón de voto
            async def callback(interaction, obj=objetivo):
                votante = interaction.user

                # Validamos que el votante esté vivo
                if votante not in partida["vivos"]:
                    await interaction.response.send_message("🚫 No estás vivo en la partida.", ephemeral=True)
                    return
                
                # Validamos que no haya votado ya
                if votante in votos:
                    await interaction.response.send_message("⚠️ Ya votaste.", ephemeral=True)
                    return

                # Registramos el voto
                votos[votante] = obj
                await interaction.response.send_message(f"✅ Votaste por **{obj.display_name}**.", ephemeral=True)

            # Asignamos el callback al botón
            button.callback = callback
            view.add_item(button)

        # Enviamos el mensaje con los botones de votación
        await canal.send("⏳Tienen solo **60 segundos**⏳\n🔻 Hacé clic en el nombre del jugador que querés eliminar:", view=view)
        await asyncio.sleep(60) # Esperamos 60 segundos para que todos voten

        # Si hubo al menos un voto durante la votación
        if votos:
            conteo = {} # Diccionario para contar cuántos votos recibió cada jugador
            # Recorremos todos los votos y sumamos los votos para cada jugador
            for elegido in votos.values():
                conteo[elegido] = conteo.get(elegido, 0) + 1

            # Buscamos el número máximo de votos recibidos por un jugador
            max_votos = max(conteo.values())
            
            # Buscamos quiénes recibieron ese número máximo de votos (por si hay empate)
            candidatos = [jug for jug, votos in conteo.items() if votos == max_votos]
            
            # Si solo hay un jugador con más votos, ese jugador es eliminado
            if len(candidatos) == 1:
                eliminado = candidatos[0] # Lo eliminamos de la lista de vivos
                partida["vivos"].discard(eliminado)
                await canal.send(f"⚰️ **{eliminado.display_name}** fue eliminado por votación del pueblo.")
            else:
                # Si hay un empate, no se elimina a nadie y se informa
                empatados = ", ".join(j.display_name for j in candidatos)
                await canal.send(f"⚖️ ¡Empate entre **{empatados}**!\n😶 Nadie será eliminado hoy.")
        else:
            await canal.send("😶 Nadie votó. El pueblo decide no eliminar a nadie hoy.")

        # Volvemos a calcular cuántas mafias y no-mafias quedan vivos después de la votación
        vivos_roles = [partida["roles"][j] for j in partida["vivos"]]
        mafias = vivos_roles.count("mafia")
        no_mafias = len(partida["vivos"]) - mafias

        if mafias == 0:
            await anunciar_fin(canal, partida, ganadores="Ciudadanos")
            break
        elif mafias >= no_mafias:
            await anunciar_fin(canal, partida, ganadores="Mafia")
            break

        await asyncio.sleep(5)

# Función que se llama cuando la partida termina, para anunciar a los ganadores y mostrar los roles
async def anunciar_fin(canal, partida, ganadores):
    # Mensaje inicial anunciando el fin de la partida y quién ganó
    await canal.send(f"🏁 **¡LA PARTIDA HA TERMINADO!**\n🥇 **GANADORES: {ganadores.upper()}** 🎉\n🔎 Revelando roles...")

    resumen = {} # Diccionario que agrupará los nombres de los jugadores por rol
    
    # Recorremos todos los jugadores y sus roles
    for jugador, rol in partida["roles"].items():
        resumen.setdefault(rol, []).append(jugador.display_name) # Agrupamos por rol

    # Mostramos en el canal qué jugadores tenía cada rol (en orden)
    for rol in ["mafia", "doctor", "detective", "ciudadano"]:
        if rol in resumen:
            jugadores = ", ".join(resumen[rol])
            await canal.send(f"🔹 **{rol.capitalize()}s**: {jugadores}")
    
    # Mensaje final de cierre, invitando a jugar otra vez
    await canal.send("🕹️ ¡Gracias por jugar! Volvé a organizar otra partida con `!mafia crear`.")

    del partidas[canal.guild.id] # Eliminamos la partida del registro global, ya que terminó

bot.run(TOKEN) # Corremos el bot