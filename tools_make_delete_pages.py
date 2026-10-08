#!/usr/bin/env python3
"""Write the missing `delete-data.html` page for the LEGACY tier of app sub-sites.

WHAT THIS DOES
  For every app in LEGACY below, writes

      <slug>/delete-data.html     the Google Play "Data deletion URL"

  Six slugs were live but had no deletion page at all - `collect-the-coins`,
  `countdowncrew`, `knowsme`, `mememic`, `outfitrate` and `qr-forge` - while
  `CLOUDYNI_URLS.md` and `PLAY_CONSOLE_URLS.md` both promised
  `https://cloudyni.com/<slug>/delete-data.html` for each of them. Google Play
  validates that field, so every one of those URLs answered 404 for a real
  Play Console field: the point of this file is that it stops.

WHY IT IS SEPARATE FROM tools_unify_app_pages.py
  That tool owns the MODERN tier: apps whose privacy/terms/delete-data pages are all
  generated from one reconciled table into the shared `styles.css` shell. This tier is
  different in two ways, and both are deliberate:

    * their privacy.html and terms.html are hand-written and are NOT regenerated here,
      so this tool must never touch them - it writes delete-data.html and nothing else;
    * five of the six are self-contained pages (one inline `<style>`, no `styles.css`
      in the directory), so a delete-data page in the shared shell would be the only
      page on the site that looked like a different product. Those five get the same
      self-contained treatment, carrying their own palette. `qr-forge` does have a
      `styles.css` and a shared-shell privacy page, so it gets the shared shell.

SOURCE OF TRUTH
  Every fact below is taken from the app's own shipped pages and manifest in this repo:
  the package ID and one-time vs subscription products from that app's `terms.html`,
  the on-device data list from its `privacy.html`. Nothing is invented, and no price is
  quoted for a product Play is the merchant of record for - the wording says "the price
  shown in Google Play at the time of purchase", exactly as the modern tier does.

USAGE
    python tools_make_delete_pages.py            # write the page for every LEGACY app
    python tools_make_delete_pages.py --check     # dry run; exit 1 if anything would change
    python tools_make_delete_pages.py --list      # show the slugs and their billing shape
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import textwrap

ROOT = pathlib.Path(__file__).resolve().parent
SITE = "https://cloudyni.com"
EMAIL = "support@cloudyni.com"
CONTROLLER = "Cloudy NI (sole trader)"
ICO = "ZC222090"
ICO_URL = "https://ico.org.uk"
PLAY = "https://play.google.com/store/apps/details?id="
POLICY_DATE = "5 October 2026"
DELETION_DAYS = "30 days"


def app(**kw):
    """One legacy app: identity, palette, and the facts its deletion page states."""
    d = dict(
        shell="bespoke",          # "bespoke" (inline <style>) or "fleet" (shared styles.css)
        brand_mark="&#9670;",     # the glyph used beside the app name in a bespoke header
        favicon="",               # relative favicon, when the site has one
        logo="",                  # emoji/glyph shown in the bespoke header
        tagline="",               # the one-line promise on its privacy page header
        blurb="",                 # the sentence under "Delete your data"
        # palette (bespoke shell only)
        bg="#f0f5fa", card="#ffffff", ink="#1c1c1c", head="#1B2430",
        head_to="#2E3D4E", head_text="#ffffff", accent="#1E88E5", border="rgba(0,0,0,0.08)",
        # facts
        storage=[],               # what the app saved on the phone
        keeps=[],                 # what survives a deletion, and why
        server="none",            # "none" or a paragraph explaining the server-side copy
        has_subscription=False,   # True when a monthly product exists (so Play cancel matters)
        billing="",               # the products, in Play's own framing
        ads="",                   # the advertising sentence
        children="",
    )
    d.update(kw)
    return d


LEGACY = [
    app(
        slug="collect-the-coins",
        name="Collect the Coins",
        package="com.cloudyni.collectthecoins",
        theme="#1B2430",
        logo="&#128055;",                      # the piggy from the app's own header
        tagline="Your coins, your gems, your device.",
        blurb=(
            "Everything Collect the Coins saves is on your phone, so clearing the app's storage "
            "deletes all of it in a couple of taps. There is no account, and no server of ours holds "
            "a copy."
        ),
        bg="#f0f5fa", card="#ffffff", ink="#1c1c1c", head="#1B2430", head_to="#2E3D4E",
        head_text="#FFC93C", accent="#1E88E5",
        storage=[
            "<strong>Game progress.</strong> Cash, gems, the current stage, machine upgrades and the coins still on the board.",
            "<strong>The board themes you own,</strong> and the one it last used.",
            "<strong>Preferences.</strong> Tutorial completion, sound and haptics settings, and the local record of the Premium purchase.",
        ],
        keeps=[
            "The purchase itself, which is a record Google holds against your Google account &mdash; not data we can delete.",
            "The advertising identifier held by Google AdMob, where advertising was served. You control that from Android settings (see below).",
        ],
        server="none",
        billing=(
            "Collect the Coins sells <strong>two one-time products</strong> through Google Play: "
            "<strong>Premium</strong>, which removes the banner, makes boosts instant and unlocks the "
            "Royal theme, and a <strong>Gem Pack</strong>. Neither is a subscription, so there is "
            "nothing to cancel, and deleting your data does not take either away &mdash; reinstalling "
            "and signing in with the same Google account restores them."
        ),
        ads=(
            "The free version shows a small banner and optional rewarded ads served by "
            "<strong>Google AdMob</strong>. A rewarded ad only ever plays when you tap the button."
        ),
        children=(
            "Collect the Coins is rated PEGI 3 and suits all ages. It has no account and no profile, so "
            "we hold nothing about a child that could be deleted."
        ),
    ),
    app(
        slug="countdowncrew",
        name="Countdown Crew",
        package="com.cloudyni.countdowncrew",
        theme="#0D1B2A",
        logo="&#9200;",
        tagline="Countdowns shared with your crew &mdash; private by design.",
        blurb=(
            "Your countdowns live on your phone. If you used a <em>shared</em> countdown, a copy of "
            "that countdown also exists in our Firebase project, and this page is how you get rid of "
            "both."
        ),
        bg="#f0f5fa", card="#ffffff", ink="#1c1c1c", head="#0D1B2A", head_to="#1E88E5",
        head_text="#ffffff", accent="#1E88E5",
        storage=[
            "<strong>Countdowns.</strong> Titles, target dates, cover emoji and the member list.",
            "<strong>Comments.</strong> Premium comment threads are stored on the device.",
            "<strong>Your display name</strong> &mdash; the name other members see when you join a shared countdown.",
            "<strong>Preferences.</strong> Milestone notifications, and the local record of your subscription or unlock.",
        ],
        keeps=[
            "A shared countdown's rows in Firebase, which are the copy other members see. Ask us and we delete them &mdash; see the next section.",
            "The purchase record Google holds, which is not ours to delete.",
        ],
        server=(
            "Sharing is <strong>opt-in</strong>. Nothing is uploaded unless you create or join a shared "
            "countdown, and when you do, only the countdown itself is: its title, target date, cover "
            "emoji, the member display names, and the premium comments. Your email address and phone "
            "number are never collected. That copy is server-side, so it is the one thing on this page "
            "that clearing your phone cannot reach &mdash; email <a "
            "href=\"mailto:support@cloudyni.com\">support@cloudyni.com</a> and we delete the shared "
            "rows within %s." % DELETION_DAYS
        ),
        has_subscription=True,
        billing=(
            "Premium is sold through Google Play as an <strong>auto-renewing monthly "
            "subscription</strong>, or as a <strong>one-off per-countdown unlock</strong>. If you took "
            "the subscription it renews until you cancel it in Google Play, and deleting your data "
            "does <em>not</em> cancel it."
        ),
        ads="Countdown Crew shows no advertising.",
        children=(
            "Countdown Crew is not directed to children under 13, and we do not knowingly collect "
            "personal information from children."
        ),
    ),
    app(
        slug="knowsme",
        name="Who Knows Me Best?",
        package="com.cloudyni.knowsme",
        theme="#1B2A41",
        logo="&#127922;",
        tagline="Your quizzes and answers stay on your device.",
        blurb=(
            "Quizzes, answers and scores are kept on your phone. If you played with syncing enabled, "
            "the quiz data needed to run the lobby is also held in our Firebase project, and this page "
            "covers both."
        ),
        bg="#f0f4fa", card="#ffffff", ink="#1c1c1c", head="#1B2A41", head_to="#FFD54F",
        head_text="#ffffff", accent="#1E88E5",
        storage=[
            "<strong>Quizzes.</strong> Titles, questions, the correct answers and join codes.",
            "<strong>Your display name,</strong> which appears in lobbies and on the leaderboard.",
            "<strong>Scores and guesses</strong> from each round.",
            "<strong>Preferences,</strong> including the local record of your subscription or pack purchase.",
        ],
        keeps=[
            "A synced quiz's rows in Firebase, which the other players' devices read. Email us and we remove them.",
            "The purchase record Google holds against your Google account.",
        ],
        server=(
            "Syncing is <strong>opt-in</strong>, and only a quiz you have shared reaches us: its "
            "questions, correct answers, join code, and the display names and scores of the players in "
            "that lobby. Your email address and phone number are never collected. Clearing your phone "
            "does not reach the server copy, so to have a shared quiz removed from our project, email "
            "<a href=\"mailto:support@cloudyni.com\">support@cloudyni.com</a> with its join code and we "
            "delete it within %s." % DELETION_DAYS
        ),
        has_subscription=True,
        billing=(
            "Premium is sold through Google Play as an <strong>auto-renewing monthly "
            "subscription</strong>, or as a <strong>one-off themed question pack</strong>. A "
            "subscription renews until you cancel it in Google Play, and deleting your data does "
            "<em>not</em> cancel it."
        ),
        ads="Who Knows Me Best? shows no advertising.",
        children=(
            "Who Knows Me Best? is not directed to children under 13, and we do not knowingly collect "
            "personal information from children."
        ),
    ),
    app(
        slug="mememic",
        name="MemeMic",
        full_name="MemeMic - Voice Changer &amp; Soundboard",
        package="com.cloudyni.mememic",
        theme="#7C4DFF",
        logo="&#127908;",
        tagline="Fun audio stays on your device &mdash; we don't hear anything.",
        blurb=(
            "Your voice is processed in real time on the phone and is never uploaded. The only things "
            "MemeMic keeps are the clips you deliberately record and your own settings, all in the "
            "app's private storage."
        ),
        bg="#f5f3ff", card="#ffffff", ink="#1c1c1c", head="#7C4DFF", head_to="#4FC3F7",
        head_text="#ffffff", accent="#7C4DFF",
        storage=[
            "<strong>Saved clips.</strong> Each time you tap Record, the processed audio is written to the app's private storage as a WAV file. Nothing is saved without that tap.",
            "<strong>Preferences.</strong> Your chosen voice effect, output device and gain.",
            "<strong>Downloaded meme packs,</strong> kept in the app's cache.",
            "<strong>The local record of your subscription.</strong>",
        ],
        keeps=[
            "The purchase record Google holds against your Google account.",
            "The advertising identifier held by Google AdMob, where advertising was served. You control that from Android settings (see below).",
            "Nothing of your voice: audio is processed in memory, and a clip exists only if you recorded one.",
        ],
        server=(
            "There is <strong>no server-side audio processing and no cloud recording</strong>, so we "
            "hold no recording of you to delete. The app does fetch premium meme packs from a content "
            "delivery network, which logs ordinary web requests (including an IP address) briefly for "
            "delivery; those logs are the network's, not a copy of your audio, and they expire on their "
            "own schedule."
        ),
        has_subscription=True,
        billing=(
            "Premium is sold through Google Play as an <strong>auto-renewing monthly "
            "subscription</strong>. It renews until you cancel it in Google Play (Play &rarr; "
            "<em>Payments &amp; subscriptions</em> &rarr; <em>Subscriptions</em>), and deleting your "
            "data or uninstalling the app does <em>not</em> cancel it."
        ),
        ads=(
            "The free version shows advertising served by <strong>Google AdMob</strong>, which may "
            "process your advertising ID and device information. You can reset or limit it from "
            "Android settings."
        ),
        children=(
            "MemeMic is not directed to children under 13, and we do not knowingly collect personal "
            "information from children."
        ),
    ),
    app(
        slug="outfitrate",
        name="OutfitRate",
        package="com.cloudyni.outfitrate",
        theme="#1A1033",
        logo="&#128087;",
        tagline="Rate outfits, search by tag &mdash; your data stays on your device.",
        blurb=(
            "Your photos, tags and ratings are stored in the app's private storage on the phone. We "
            "hold no server copy of them in this version, so clearing the app's storage deletes all of "
            "it at once."
        ),
        bg="#f8f0ff", card="#ffffff", ink="#1c1c1c", head="#1A1033", head_to="#7C4DFF",
        head_text="#ffffff", h2_color="#7C4DFF", accent="#7C4DFF",
        storage=[
            "<strong>Uploaded outfit photos,</strong> kept in the app's private storage.",
            "<strong>Your tags</strong> (tops, bottoms, shoes, accessories and so on).",
            "<strong>Your ratings</strong> of other outfits, and the outfits you saved.",
            "<strong>Moderation reports</strong> you filed, held locally for review.",
            "<strong>Preferences,</strong> including your display name and the local record of your subscription.",
        ],
        keeps=[
            "The purchase record Google holds against your Google account.",
            "Anything you chose to share with another player, which is theirs to delete as well.",
        ],
        server="none",
        has_subscription=True,
        billing=(
            "Premium is sold through Google Play as an <strong>auto-renewing monthly "
            "subscription</strong>. It renews until you cancel it in Google Play (Play &rarr; "
            "<em>Payments &amp; subscriptions</em> &rarr; <em>Subscriptions</em>), and deleting your "
            "data or uninstalling the app does <em>not</em> cancel it."
        ),
        ads="OutfitRate shows no third-party advertising.",
        children=(
            "OutfitRate is not directed to children under 13, and we do not knowingly collect personal "
            "information from children. Community moderation, including the report button on every "
            "outfit, stays in place before any publishing."
        ),
    ),
    app(
        slug="qr-forge",
        name="QR Forge",
        package="com.cloudyni.qr_forge",
        theme="#7C5CFF",
        shell="fleet",                        # this site has styles.css + a shared-shell privacy page
        brand_mark="&#9672;",                 # the same diamond as the rest of the qr-forge site
        favicon="",
        tagline="Create QR codes, on your device.",
        blurb=(
            "QR Forge has no account, no backend and no analytics, so there is nothing of yours on our "
            "servers. Everything it saved &mdash; your history, labels, colours and settings &mdash; is "
            "in the app's private storage on the phone."
        ),
        storage=[
            "<strong>Saved QR codes.</strong> The payloads you chose to keep in History, with their labels and styling.",
            "<strong>Preferences.</strong> The last type, colours, gradient and module style you used.",
            "<strong>The local record of your subscription or lifetime purchase.</strong>",
        ],
        keeps=[
            "The purchase record Google holds against your Google account.",
            "The advertising identifier held by Google AdMob, where advertising was served. You control that from Android settings (see below).",
        ],
        server="none",
        has_subscription=True,
        billing=(
            "QR Forge sells two products through Google Play: <code>premium_monthly</code>, a "
            "recurring subscription, and <code>premium_lifetime</code>, a one-time purchase that keeps "
            "Premium indefinitely. They are separate products &mdash; buying one does not grant the "
            "other. If you took the subscription, cancel it in Google Play (Play &rarr; <em>Payments "
            "&amp; subscriptions</em> &rarr; <em>Subscriptions</em>); deleting your data does not "
            "cancel it."
        ),
        ads=(
            "The free version shows advertising served by <strong>Google AdMob</strong>. Where the law "
            "requires it, the app first asks for consent through <strong>Google's User Messaging "
            "Platform</strong>, and no personalised ad is requested until that consent flow completes."
        ),
        children=(
            "QR Forge is not directed to children under 13, and we do not knowingly collect personal "
            "information from children."
        ),
    ),
]


# ---------------------------------------------------------------------------
# Page furniture, shared by both shells
# ---------------------------------------------------------------------------
def p(html):
    return "    <p>\n      %s\n    </p>\n" % html


def h2(anchor, title):
    return '    <h2 id="%s">%s</h2>\n' % (anchor, title)


def ul(items):
    return "".join("      <li>%s</li>\n" % i for i in items)


def ol(items):
    return "".join("      <li>%s</li>\n" % i for i in items)


def toc(items):
    out = '    <nav class="toc" aria-label="On this page">\n'
    out += "      <strong>On this page</strong>\n      <ul>\n"
    for anchor, label in items:
        out += '        <li><a href="#%s">%s</a></li>\n' % (anchor, label)
    out += "      </ul>\n    </nav>\n"
    return out


def meta_rows(app):
    return [
        ("App", "%s &middot; Android package <code>%s</code>" % (app["name"], app["package"])),
        ("Data controller", CONTROLLER),
        ("ICO data protection registration",
         '<a href="%s" rel="noopener" target="_blank">%s</a>' % (ICO_URL, ICO)),
        ("Region", "Northern Ireland, United Kingdom"),
        ("Last updated", POLICY_DATE),
        ("Contact", '<a href="mailto:%s">%s</a>' % (EMAIL, EMAIL)),
        ("Deletion requests completed", "Within %s" % DELETION_DAYS),
    ]


def delete_sections(app):
    """Every section of the page, in order, as (anchor, label, html)."""
    sections = []

    # 1. what the app kept on the phone, and how to remove it
    device = [
        p("You do not have to ask us for anything. Everything %s saved is in the app's private "
          "storage, and Android removes it in a couple of taps:" % app["name"]),
        "    <ol>\n" + ol([
            "Open Android <strong>Settings</strong> &rarr; <strong>Apps</strong> &rarr; "
            "<strong>%s</strong>." % app["name"],
            "Tap <strong>Storage</strong>, then <strong>Clear storage</strong>. That erases every "
            "entry, preference and cached file in one step.",
            "To remove the app as well, tap <strong>Uninstall</strong> &mdash; or hold the app's "
            "icon on your home screen and choose <strong>Uninstall</strong>.",
        ]) + "    </ol>\n",
        p("That covers:"),
        "    <ul>\n" + ul(app["storage"]) + "    </ul>\n",
    ]
    sections.append(("device", "Delete what is on your device", "".join(device)))

    # 2. the account / server-side question, answered honestly for this app
    if app["server"] == "none":
        account = [
            p("%s has <strong>no sign-in and no account</strong>, so there is no profile to delete "
              "and nothing of yours on our servers. %s" % (app["name"], app["blurb"])),
        ]
        label = "There is no account and no server copy"
    else:
        account = [
            p("%s has <strong>no sign-in and no account</strong>, so there is no profile to delete. "
              "Nothing is uploaded unless you switched sharing on." % app["name"]),
            p(app["server"]),
        ]
        label = "Shared data we hold, and how to remove it"
    sections.append(("account", label, "".join(account)))

    # 3. email route, for anything the phone cannot reach
    sections.append((
        "email",
        "Ask us to delete it by email",
        p('Email <a href="mailto:%s">%s</a> with the app name and your Google Play order number if '
          'you have it. We will confirm in writing, and the request is completed within %s. If your '
          'message is about data on the phone, clearing the app\'s storage yourself is faster and '
          'just as final.' % (EMAIL, EMAIL, DELETION_DAYS)),
    ))

    # 4. what survives
    keeps = [p("Deleting your data is permanent &mdash; once it is gone we cannot restore it, so "
               "keep anything you want to keep first. Two things are not ours to delete:") ,
             "    <ul>\n" + ul(app["keeps"]) + "    </ul>\n"]
    if app["ads"]:
        keeps.append(p("%s" % app["ads"]))
        keeps.append(p('To reset or delete your advertising ID, or turn personalised advertising off, '
                       'open Android <strong>Settings</strong> &rarr; <strong>Privacy</strong> &rarr; '
                       '<strong>Ads</strong>.'))
    sections.append(("what", "What that deletes, and what stays", "".join(keeps)))

    # 5. billing
    heading = ("Deleting data does not cancel a subscription"
               if app["has_subscription"] else "Your purchase is not affected")
    sections.append(("billing", heading, p(app["billing"])))

    # 6. the Play declaration
    if app["server"] == "none":
        account_line = ("Users can create an account &mdash; <strong>no</strong>. There is no "
                        "sign-in, no account and no server-side profile.")
    else:
        account_line = ("Users can create an account &mdash; <strong>no</strong>. There is no "
                        "sign-in and no account; sharing is a per-countdown/per-quiz choice, not a "
                        "profile.")
    play = [
        p("Google Play asks for a Data safety declaration for every app. These are the lines we "
          "declare for this build, and they match the sections above:"),
        "    <ul>\n" + ul([
            account_line,
            "Account creation is <strong>not required</strong> and is not available in this version.",
            "Users can request deletion &mdash; <strong>yes</strong> (clearing app storage or "
            "uninstalling erases everything at once; this page is the deletion URL, and support can "
            "confirm in writing if you need it).",
            "Deletion requests are completed within <strong>%s</strong>." % DELETION_DAYS,
        ]) + "    </ul>\n",
        p("%s" % app["children"]),
    ]
    sections.append(("play", "What we declare to Google Play", "".join(play)))
    return sections


def meta_block(app):
    body = "".join("      <strong>%s:</strong> %s<br />\n" % (k, v) for k, v in meta_rows(app))
    return '    <p class="meta">\n%s    </p>\n' % body


def btn_row(app, fleet):
    primary = "btn btn-primary" if fleet else "btn"
    secondary = "btn btn-secondary" if fleet else "btn"
    out = '    <div class="btn-row" style="margin:2rem 0 0">\n'
    out += '      <a class="%s" href="%s%s" rel="noopener" target="_blank">Get %s on Google Play</a>\n' % (
        primary, PLAY, app["package"], app["name"])
    out += '      <a class="%s" href="../index.html">See all our apps</a>\n' % secondary
    out += "    </div>\n"
    return out


# Classes qr-forge/styles.css defines, from its own selector list. The two it does not define are
# stubbed inline in the palette it already ships, the way that site already styles its hero card
# inline - growing styles.css for a single page would be the wrong trade.
FLEET_STYLE = """  <style>
    /* Only the two components this site\'s stylesheet has no rule for yet. */
    .legal-body .toc {
      border: 1px solid var(--border); border-radius: 14px;
      background: var(--surface); padding: 1rem 1.15rem; margin: 1.25rem 0 0;
    }
    .legal-body .toc strong { color: var(--ink); font-size: 0.95rem; }
    .legal-body .toc ul { padding-left: 1.1rem; margin: 0.45rem 0 0; }
    .legal-body .toc li { margin: 0.15rem 0; }
    .legal-body .note {
      border: 1px solid var(--border); border-left: 3px solid var(--accent);
      border-radius: 12px; background: rgba(124,92,255,0.08);
      padding: 1rem 1.15rem; margin: 1.25rem 0 0;
    }
  </style>
"""

BESPOKE_STYLE = """  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { font-family: system-ui, -apple-system, sans-serif; line-height: 1.7; color: %(ink)s; background: %(bg)s; }
    header { background: linear-gradient(135deg, %(head)s, %(head_to)s); color: #fff; padding: 2.5rem 1rem; text-align: center; }
    header h1 { font-size: 2rem; color: %(head_text)s; }
    header p { opacity: 0.92; margin-top: 0.4rem; font-size: 0.95rem; }
    main { max-width: 780px; margin: 0 auto; padding: 2rem 1rem 3rem; }
    .card { background: %(card)s; border-radius: 16px; padding: 2rem; box-shadow: 0 2px 12px rgba(0,0,0,0.08); }
    h2 { color: %(h2)s; margin: 1.8rem 0 0.6rem; font-size: 1.25rem; }
    h2:first-child { margin-top: 0; }
    p, li { color: %(ink)s; }
    ul, ol { padding-left: 1.4rem; margin: 0.6rem 0; }
    li { margin: 0.35rem 0; }
    a { color: %(accent)s; }
    .updated { font-size: 0.9rem; color: %(muted)s; margin-bottom: 1.2rem; }
    .meta { font-size: 0.92rem; color: %(muted)s; line-height: 1.8; margin-bottom: 1.2rem; }
    .meta code { background: %(bg)s; padding: 0.1em 0.35em; border-radius: 5px; }
    .note { background: %(bg)s; border-left: 4px solid %(h2)s; border-radius: 10px; padding: 1rem 1.15rem; margin-bottom: 1.3rem; font-size: 0.98rem; }
    .toc { background: %(bg)s; border-radius: 12px; padding: 1rem 1.2rem; margin-bottom: 1.4rem; font-size: 0.95rem; }
    .toc ul { list-style: none; padding-left: 0; margin: 0.45rem 0 0; }
    .toc li { margin: 0.15rem 0; }
    .btn { display: inline-block; margin-top: 1.4rem; background: %(h2)s; color: #fff !important; text-decoration: none; font-weight: 700; padding: 0.7rem 1.4rem; border-radius: 999px; }
    .btn + .btn { margin-left: 0.6rem; }
    footer { text-align: center; padding: 2rem 1rem; color: %(muted)s; font-size: 0.9rem; }
    footer a { color: %(accent)s; }
  </style>
"""


def desc(app):
    return ("How to delete your %s data: what clearing the app's storage removes, and how to ask us "
            "to delete anything else." % app["name"])


def body(app):
    """Everything between the page's opening and its closing button row."""
    sections = delete_sections(app)
    out = meta_block(app)
    out += '    <div class="note">\n      <p>%s</p>\n    </div>\n' % app["blurb"]
    out += toc([(a, l) for a, l, _ in sections])
    for anchor, label, html in sections:
        out += h2(anchor, label) + html
    return out


def head_html(app, extra=""):
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en-GB">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        "  <title>Delete your data &mdash; %s</title>\n" % app["name"]
        + '  <meta name="description" content="%s" />\n' % desc(app)
        + '  <meta name="theme-color" content="%s" />\n' % app["theme"]
        + '  <meta name="robots" content="index,follow" />\n'
        + '  <link rel="canonical" href="%s/%s/delete-data.html" />\n' % (SITE, app["slug"])
        + extra
        + "</head>\n"
    )


def render_bespoke(app):
    """The self-contained shell: one inline stylesheet in the app's own palette, no styles.css."""
    style = BESPOKE_STYLE % dict(
        ink=app["ink"], bg=app["bg"], head=app["head"], head_to=app["head_to"],
        head_text=app["head_text"], card=app["card"],
        h2=app.get("h2_color") or app["head"], accent=app["accent"],
        muted=app.get("muted") or "#667085",
    )
    out = head_html(app, style)
    out += "<body>\n"
    out += (
        "  <header>\n"
        "    <h1>%s %s: delete your data</h1>\n" % (app["logo"], app["name"])
        + "    <p>Data controller: %s</p>\n" % CONTROLLER
        + '    <p>ICO data protection registration: <a href="%s" rel="noopener" target="_blank" '
          'style="color:#fff;text-decoration:underline">%s</a></p>\n' % (ICO_URL, ICO)
        + "    <p>%s</p>\n" % app["tagline"]
        + "  </header>\n"
    )
    out += '  <main>\n    <div class="card">\n'
    out += '      <p class="updated">Last updated: %s</p>\n' % POLICY_DATE
    out += textwrap.indent(body(app), "  ")
    out += btn_row(app, fleet=False)
    out += "    </div>\n  </main>\n"
    out += (
        "  <footer>\n"
        "    &copy; 2026 CloudyNI &middot; "
        '<a href="index.html">%s home</a> &middot; '
        '<a href="privacy.html">Privacy</a> &middot; '
        '<a href="terms.html">Terms</a> &middot; '
        '<a href="mailto:%s">Contact</a>\n'
        "  </footer>\n"
        "</body>\n</html>\n" % (app["name"], EMAIL)
    )
    return out


def render_fleet(app):
    """The shared shell (styles.css), for a site that already ships one: qr-forge."""
    out = head_html(app, '  <link rel="stylesheet" href="styles.css" />\n' + FLEET_STYLE)
    out += "<body>\n"
    out += '  <div class="page-bg" aria-hidden="true"></div>\n\n'
    out += (
        '  <header class="site-header">\n'
        '    <div class="inner">\n'
        '      <a class="brand" href="index.html"><span class="brand-mark">%s</span> %s</a>\n'
        '      <nav class="nav" aria-label="Main">\n'
        '        <a href="index.html">Home</a>\n'
        '        <a href="privacy.html">Privacy</a>\n'
        '        <a href="terms.html">Terms</a>\n'
        '        <a href="delete-data.html" aria-current="page">Delete data</a>\n'
        '        <a href="%s%s" class="nav-cta">Get the app</a>\n'
        "      </nav>\n    </div>\n  </header>\n\n"
        % (app["brand_mark"], app["name"], PLAY, app["package"])
    )
    out += '  <main class="wrap legal-body">\n'
    out += "    <h1>Delete your data</h1>\n"
    out += textwrap.indent(body(app), "  ")
    out += btn_row(app, fleet=True)
    out += "\n  </main>\n\n"
    out += (
        '  <footer class="site-footer">\n'
        '    <div class="inner">\n'
        '      <span class="brand"><span class="brand-mark">%s</span> %s</span>\n'
        "      <p>Published by CloudyNI &middot; Built for Android</p>\n"
        '      <nav class="nav">\n'
        '        <a href="index.html">Home</a>\n'
        '        <a href="privacy.html">Privacy</a>\n'
        '        <a href="terms.html">Terms</a>\n'
        '        <a href="delete-data.html">Delete data</a>\n'
        "      </nav>\n    </div>\n  </footer>\n"
        "</body>\n</html>\n" % (app["brand_mark"], app["name"])
    )
    return out


def build(app):
    return render_fleet(app) if app["shell"] == "fleet" else render_bespoke(app)


def write_page(path, text, check, changes):
    rel = path.relative_to(ROOT).as_posix()
    old = None
    if path.exists():
        old = path.read_text(encoding="utf-8").replace("\r\n", "\n")
    if old == text:
        print("  same        %s" % rel)
        return False
    changes.append(rel)
    if check:
        print("  would write %s%s" % (rel, "" if old is not None else "  (new file)"))
        return True
    path.write_text(text, encoding="utf-8", newline="\n")
    print("  %s %s" % ("created    " if old is None else "updated    ", rel))
    return True


def internal_link_problems(pages):
    """Every local href in a generated page must resolve to a real file."""
    problems = []
    for path, text in pages:
        for href in sorted(set(re.findall(r'href="([^"]+)"', text))):
            if href.startswith(("#", "http://", "https://", "mailto:", "tel:", "data:")):
                continue
            target = (path.parent / href.split("#")[0]).resolve()
            if href.endswith("/") or target.is_dir():
                target = target / "index.html"
            # A page links to itself in its own nav and footer; that resolves the moment it exists.
            if target == path.resolve():
                continue
            if not target.exists():
                problems.append("%s -> %s" % (path.relative_to(ROOT).as_posix(), href))
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tools_make_delete_pages.py",
        description="Write delete-data.html for the LEGACY tier of app sub-sites.",
    )
    parser.add_argument("--check", action="store_true",
                        help="dry run: report what would change, and exit 1 if anything would")
    parser.add_argument("--list", action="store_true",
                        help="list the slugs, shells and billing shape, then exit")
    args = parser.parse_args(argv)

    seen = set()
    for a in LEGACY:
        if a["slug"] in seen:
            raise SystemExit("duplicate slug in LEGACY: %s" % a["slug"])
        seen.add(a["slug"])

    if args.list:
        print("%-20s %-9s %-13s %s" % ("SLUG", "SHELL", "BILLING", "APP"))
        for a in LEGACY:
            print("%-20s %-9s %-13s %s" % (
                a["slug"], a["shell"],
                "subscription" if a["has_subscription"] else "one-off",
                a["name"]))
        return 0

    pages = []
    for a in LEGACY:
        base = ROOT / a["slug"]
        if not base.is_dir():
            print("no such directory: %s" % base, file=sys.stderr)
            return 2
        pages.append((base / "delete-data.html", build(a)))

    changes = []
    for path, text in pages:
        write_page(path, text, args.check, changes)

    problems = internal_link_problems(pages)
    for problem in problems:
        print("BROKEN LINK  %s" % problem)

    if args.check:
        print("\n--check: %d file(s) would change, %d broken link(s)"
              % (len(changes), len(problems)))
        return 1 if (changes or problems) else 0

    print("\n%d file(s) written, %d broken link(s)" % (len(changes), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

