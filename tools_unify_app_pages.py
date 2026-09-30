#!/usr/bin/env python3
"""Regenerate the unified legal pages for every Cloudy NI app sub-site in this repo.

WHAT THIS DOES
  Rewrites, for every canonical app slug:

      <slug>/privacy.html      Privacy policy      (reconciled with the shipped app)
      <slug>/terms.html        Terms of use        (Google Play billing wording)
      <slug>/delete-data.html  Data deletion URL   (Google Play Data-deletion URL)

  It also writes `noindex` redirect stubs for retired alias slugs so old links and
  Play Console entries keep working.

WHAT IT DOES NOT DO
  index.html is a bespoke marketing page per app and is never generated here. Edit
  those by hand. styles.css is a per-app themed copy and is never touched.

SOURCE OF TRUTH
  Each entry in APPS below was reconciled against the app's own manifest
  (android/app/build.gradle, pubspec.yaml, package.json) and the fleet audit at
  _fleet/audits/master/. If an app adds a processor or a product, add it here and
  re-run; do not hand-edit the generated pages.

HOUSE RULES BAKED IN
  * Contact address is support@cloudyni.com everywhere.
  * Data controller: Cloudy NI (sole trader), Northern Ireland, ICO registration
    ZC222090.
  * NO hard-coded prices. Subscription prices are always "the price shown in Google
    Play at the time of purchase", because Play is the merchant of record and a
    stale price in a policy page is a compliance defect.
  * Product IDs are quoted (they are verifiable identifiers), prices are not.
  * A page may only claim a processor the app actually ships. "No cloud accounts"
    claims are only made for apps with no Supabase/Firebase auth at all.

USAGE
    python tools_unify_app_pages.py                 # write every page
    python tools_unify_app_pages.py --check         # dry run; exit 1 if anything would change
    python tools_unify_app_pages.py --app pa-mic     # one slug only
    python tools_unify_app_pages.py --list           # list slugs and modes
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import textwrap
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent
SITE = "https://cloudyni.com"
EMAIL = "support@cloudyni.com"
CONTROLLER = "Cloudy NI (sole trader)"
ICO = "ZC222090"
ICO_URL = "https://ico.org.uk"
PLAY = "https://play.google.com/store/apps/details?id="

# Shared Google host used by AdMob / Firebase / Play Billing.
GOOGLE_PRIVACY = (
    '<a href="https://policies.google.com/privacy" rel="noopener noreferrer" '
    'target="_blank">Google Privacy Policy</a>'
)
SUPABASE_PRIVACY = (
    '<a href="https://supabase.com/privacy" rel="noopener noreferrer" '
    'target="_blank">Supabase privacy policy</a>'
)
PLAY_TERMS = (
    '<a href="https://play.google.com/intl/en_GB/about/play-terms/" '
    'rel="noopener noreferrer" target="_blank">Google Play Terms of Service</a>'
)

# ---------------------------------------------------------------------------
# Firebase service lists, named once so the wording cannot drift between apps.
# ---------------------------------------------------------------------------
FB_GA = "Google Analytics for Firebase (anonymous usage analytics)"
FB_CRASH = "Firebase Crashlytics (crash and error diagnostics)"
FB_PERF = "Firebase Performance Monitoring"
FB_RC = "Firebase Remote Config"
FB_FCM = "Firebase Cloud Messaging (push notifications)"

FB_FULL = [FB_GA, FB_CRASH, FB_PERF, FB_RC, FB_FCM]

# Cloud posture labels used by the privacy and terms builders.
CLOUD_NONE = "none"           # no Supabase/Firebase auth at all
CLOUD_OPTIN_E2E = "optin_e2e"  # optional account + end-to-end encrypted backup
CLOUD_LIVE_SYNC = "live_sync"  # optional household sharing, server-readable rows
CLOUD_GATED_OFF = "gated_off"  # client code exists but the backend is disabled


# ---------------------------------------------------------------------------
# Page furniture
# ---------------------------------------------------------------------------
def head(app, page, title, desc, noindex=False):
    fav = app["favicon"]
    if fav.startswith("assets/"):
        fav = '<link rel="icon" type="image/png" href="%s" />' % fav
    else:
        fav = '<link rel="icon" href="%s" />' % fav
    robots = (
        '<meta name="robots" content="noindex,follow" />\n  '
        if noindex
        else '<meta name="robots" content="index,follow" />\n  '
    )
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en-GB">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        "  <title>%s</title>\n"
        '  <meta name="description" content="%s" />\n'
        '  <meta name="theme-color" content="%s" />\n'
        "  %s"
        '  <link rel="canonical" href="%s/%s/%s" />\n'
        '  <link rel="stylesheet" href="styles.css" />\n'
        "  %s\n"
        "</head>\n"
        "<body>\n"
        '  <div class="page-bg" aria-hidden="true"></div>\n'
        % (title, desc, app["theme"], robots, SITE, app["slug"], page, fav)
    )


def brand(app):
    if app["favicon"].startswith("data:"):
        return '<span class="brand-mark" aria-hidden="true">&#9670;</span> %s' % app[
            "name"
        ]
    return (
        '<img src="%s" width="38" height="38" alt="" /> %s'
        % (app["favicon"], app["name"])
    )


def header(app, active):
    def link(href, label, key):
        cur = ' aria-current="page"' if active == key else ""
        return '        <a href="%s"%s>%s</a>\n' % (href, cur, label)

    out = (
        '  <header class="site-header">\n'
        '    <div class="inner">\n'
        '      <a class="brand" href="index.html">%s</a>\n'
        '      <nav class="nav" aria-label="Main">\n' % brand(app)
    )
    out += link("index.html", "Home", "index")
    out += link("privacy.html", "Privacy", "privacy")
    out += link("terms.html", "Terms", "terms")
    out += link("delete-data.html", "Delete data", "delete-data")
    out += '        <a href="%s%s" class="nav-cta">Get the app</a>\n' % (
        PLAY,
        app["package"],
    )
    out += "      </nav>\n    </div>\n  </header>\n"
    return out


def footer(app):
    return (
        '\n  <footer class="site-footer">\n'
        '    <div class="inner footer-grid">\n'
        "      <div>\n"
        '        <strong style="color:var(--ink)">%s</strong><br />\n'
        '        Northern Ireland &middot; '
        '<a href="mailto:%s">%s</a>\n'
        "      </div>\n"
        '      <div class="footer-links">\n'
        '        <a href="index.html">Home</a>\n'
        '        <a href="privacy.html">Privacy</a>\n'
        '        <a href="terms.html">Terms</a>\n'
        '        <a href="delete-data.html">Delete data</a>\n'
        '        <a href="../index.html">All our apps</a>\n'
        "      </div>\n"
        "    </div>\n"
        '    <div class="inner" style="margin-top:1rem">\n'
        '      <p style="margin:0">&copy; 2026 %s. %s</p>\n'
        "    </div>\n"
        "  </footer>\n"
        "</body>\n"
        "</html>\n"
        % (app["name"], EMAIL, EMAIL, app["name"], app["footer_note"])
    )


def play_block(app):
    return (
        '\n    <div class="btn-row" style="margin:2rem 0 0">\n'
        '      <a class="btn btn-primary" href="%s%s" rel="noopener" target="_blank">'
        "Get %s on Google Play</a>\n"
        '      <a class="btn" href="../index.html">See all our apps</a>\n'
        "    </div>\n" % (PLAY, app["package"], app["name"])
    )


def meta_block(rows):
    body = "".join(
        "      <strong>%s:</strong> %s<br />\n" % (k, v) for k, v in rows
    )
    return '    <p class="doc-meta">\n%s    </p>\n' % body


def note(html, cls="note"):
    return '    <div class="%s">\n      %s\n    </div>\n' % (cls, html)


def toc(items):
    out = '    <nav class="toc" aria-label="On this page">\n'
    out += "      <strong>On this page</strong>\n      <ul>\n"
    for anchor, label in items:
        out += '        <li><a href="#%s">%s</a></li>\n' % (anchor, label)
    out += "      </ul>\n    </nav>\n"
    return out


def h2(anchor, title):
    return '    <h2 id="%s">%s</h2>\n' % (anchor, title)


def ul(items, indent="      "):
    out = "    <ul>\n"
    for i in items:
        out += "%s<li>%s</li>\n" % (indent, i)
    out += "    </ul>\n"
    return out


def ol(items):
    out = "    <ol>\n"
    for i in items:
        out += "      <li>%s</li>\n" % i
    out += "    </ol>\n"
    return out


def p(html):
    return "    <p>%s</p>\n" % html


def controller_row():
    return "Data controller: %s" % CONTROLLER


def ico_row():
    return (
        'ICO data protection registration: <a href="%s" rel="noopener" '
        'target="_blank">%s</a>' % (ICO_URL, ICO)
    )


# ---------------------------------------------------------------------------
# The fleet table. One entry per canonical app sub-site.
# ---------------------------------------------------------------------------
def app(**kw):
    d = dict(
        favicon="assets/icon_512.png",
        footer_note="Informational tools only — not professional advice.",
        cloud=CLOUD_NONE,
        cloud_note="",
        cloud_terms="",
        cloud_delete=None,
        services=[],
        collected=[],
        on_device=[],
        ads=None,
        consent=False,
        analytics=[],
        analytics_note=None,
        extra_processors=[],
        sensitive=None,
        children=None,
        retention=None,
        security_extra=None,
        monetisation="",
        products=[],
        # True for an app whose only paid product is a one-off. The billing wording
        # then says "there is nothing to cancel" instead of explaining how to
        # cancel a subscription, which would be wrong on an ICO-facing page.
        one_off_only=False,
        # Optional per-app override of POLICY_DATE — used when a brand-new app is
        # added and re-dating every other policy would be noise.
        policy_date=None,
        plans_note="",
        ads_terms=None,
        disclaimers=[],
        privacy_extra=[],
        terms_extra=[],
        deletion_days=30,
        support_days=90,
        play_answers=[],
        not_stored="",
    )
    d.update(kw)
    return d


# Wording reused by every app that sells through Google Play Billing.
BILLING_RENEWAL = """
      <li><strong>Auto-renewal.</strong> If the product you buy is a subscription it renews
        automatically at the end of each billing period, at the price shown in Google Play, until
        you cancel. If the product is a one-time purchase it does not renew.</li>
      <li><strong>Cancelling.</strong> Cancel in Google Play &rarr;
        <em>Payments &amp; subscriptions</em> &rarr; <em>Subscriptions</em>. Uninstalling the app
        does not cancel billing. You keep the paid features until the end of the period you have
        already paid for.</li>
      <li><strong>Refunds.</strong> Google is the merchant of record, so refunds and billing
        disputes are handled by Google under Google Play policy, not by us. We cannot issue, block
        or reverse a Google Play charge.</li>
      <li><strong>Price changes.</strong> We do not set the amount you are charged &mdash; Play
        does, and it shows the exact price (including tax) before you confirm. If a subscription
        price changes, Play notifies you and asks you to accept it before it applies.</li>
      <li><strong>Restoring a purchase.</strong> Reinstalling the app and signing in with the same
        Google account restores an active entitlement. If it does not appear, use
        <em>Restore purchases</em> in the app, then contact support.</li>
"""

CATALOGUE_NOTE = """
    <p>
      The product identifiers below are the ones the app requests from Google Play. The
      <strong>price is deliberately not fixed on this page</strong>: Play is the merchant of record
      and the amount you pay is always the amount shown on the Google Play purchase sheet when you
      confirm, including any local tax. Treat the price on that screen as the authoritative one.
    </p>
"""


# Wording reused by every app whose cloud code ships switched off (CLOUD_GATED_OFF).
# These builds have a Supabase client compiled in, but the feature flag is false, so no
# account surface exists and nothing is ever uploaded. Pages must say that, and only that.
CLOUD_OFF_NOTE = """
      <p>
        In the build you can download today this app is <strong>local-only</strong>: there is no
        account, no sign-in and no server copy of your data, so nothing about you is held on our
        servers to read, export or delete. The app's code does contain a dormant, optional
        encrypted-backup feature, but it is <strong>switched off and unreachable</strong> in this
        release &mdash; there is no control in the app that can enable it.
      </p>
      <p>
        If we ever ship that feature we will update this policy first, state exactly what a backup
        would store and where, and provide in-app controls to delete it. Until then, no data from
        this app is uploaded to us.
      </p>
    """

CLOUD_OFF_ANSWERS = [
    "Users can create an account &mdash; <strong>no</strong>. The released app has no sign-in, no account and no server-side profile.",
    "Account creation is <strong>not required</strong> and is not available in this version.",
    "Users can request deletion &mdash; <strong>yes</strong> (clearing app storage or uninstalling erases everything at once; this page is the deletion URL, and support can confirm in writing if you need it).",
    "Deletion requests are completed within <strong>30 days</strong>.",
]

APPS = [
    app(
        slug="decibel-meter-pro",
        name="Decibel Meter Pro",
        package="com.luckytools.decibel_meter_pro",
        theme="#0f766e",
        footer_note="Sound level meter — readings are indicative, not a calibrated instrument.",
        cloud=CLOUD_GATED_OFF,
        cloud_note=CLOUD_OFF_NOTE,
        services=["Microphone"],
        collected=[
            "**Sound level readings.** The microphone is used to measure loudness. Audio is analysed live in memory and is never recorded, saved to storage or uploaded &mdash; the app does not create an audio file.",
            "**Measurements you keep.** If you save a reading, the app stores the value, a label and a timestamp.",
            "**Settings.** Calibration offset, weighting, units, theme and the screen-keep-awake preference.",
            "**Advertising data** processed by Google AdMob and its mediated partner networks on the free tier (see the advertising section).",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Saved measurements, with their labels and timestamps.",
            "The running average and maximum for a session you have open.",
            "Calibration offset, weighting curve, units and theme.",
            "The locally cached Pro entitlement for this install.",
        ],
        ads="""
      The free tier shows banner and interstitial advertising served through <strong>Google
      AdMob</strong>, with <strong>Meta Audience Network</strong> and <strong>AppLovin</strong> as
      mediated partner networks that can fill those ad slots. Google and those partners may process
      your <em>advertising ID</em>, IP address and device information to serve and measure ads. This
      release does not show its own in-app advertising consent form; whether an ad is personalised is
      decided by the advertising SDKs and your Android settings, where you can reset or delete your
      advertising ID, or turn personalised advertising off, at any time. AdMob never receives your
      audio, your measurements or your saved readings.
    """,
        monetisation="""
      Decibel Meter Pro is free to download and supported by advertising. Pro features are sold as
      an <strong>auto-renewing subscription</strong> through Google Play Billing. There is
      <strong>no one-time purchase and no lifetime unlock</strong> for this app.
    """,
        products=[
            "<code>decibel_premium</code> &mdash; monthly auto-renewing subscription",
            "<code>decibel_premium_annual</code> &mdash; annual auto-renewing subscription",
        ],
        plans_note="""
      Pro removes advertising and unlocks the extra measurement features described on the app's
      Google Play listing. Both products are <strong>subscriptions</strong>: neither is a one-off
      payment, and we do not sell a lifetime unlock. If you see a claim elsewhere that Decibel
      Meter Pro is a one-time purchase, it is out of date &mdash; this page describes what the app
      actually sells.
    """,
        ads_terms="""
      The free version contains banner and interstitial advertising served through Google AdMob, with
      Meta Audience Network and AppLovin as mediated partner networks. An active Pro subscription
      removes advertising entirely for the period you have paid for.
    """,
        disclaimers=[
            "**Not a calibrated instrument.** Decibel Meter Pro uses your phone's microphone, which is not a calibrated sound level meter. Readings are indicative and vary with the device, its case, microphone condition and background noise. A real meter is calibrated to a traceable standard; this app is not.",
            "**Not for safety, health, legal or compliance decisions.** Do not rely on the app to assess workplace noise exposure, hearing-protection requirements, or any health, safety, insurance or legal matter. Use a calibrated instrument, and where required a qualified professional.",
            "**Hearing.** Sustained exposure to loud sound can damage hearing. Nothing in this app protects you from that.",
        ],
        not_stored="""
      We do not sell your data and we do not build an advertising profile of you. Your microphone
      audio never leaves the device in any form: there is no recording, no audio file and no audio
      upload. In this release your saved readings do not leave the phone either &mdash; the cloud
      backup that would carry them is switched off.
    """,
        play_answers=CLOUD_OFF_ANSWERS + [
            "Data collected: audio is <strong>not</strong> collected (processed on-device only); app activity and diagnostics may be collected; no account data is collected, because there is no account.",
        ],
    ),
    app(
        slug="pa-mic",
        name="Bluetooth Mic - Karaoke &amp; PA",
        package="com.btcmic.pamic",
        theme="#0284c7",
        favicon="assets/app-icon-512.png",
        footer_note="Audio routing tool — you control the volume and the output device.",
        cloud=CLOUD_GATED_OFF,
        cloud_note=CLOUD_OFF_NOTE,
        services=["Microphone", "Bluetooth", "Foreground service"],
        collected=[
            "**Microphone audio.** Audio is routed in real time from your microphone to the output you choose so that you can sing, speak or amplify. The app does not record your audio, does not save an audio file and does not upload audio anywhere. All processing happens live on your device.",
            "**Bluetooth devices.** Paired device names and identifiers are read so you can choose which microphone or speaker to use. On Android 12 and later this needs the <em>Nearby devices</em> permission; without it Bluetooth audio routing cannot work.",
            "**Saved presets.** The names and values of the microphone and effect setups you create &mdash; input, output, gain, echo, reverb, pitch and equaliser settings.",
            "**Diagnostics and analytics** described in the analytics section below.",
            "**Advertising data** processed by Google AdMob on the free tier.",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your presets and effect settings.",
            "The last device you connected and your audio routing choices.",
            "App preferences such as theme, keep-screen-awake and default input.",
            "The locally cached entitlement for this install.",
        ],
        ads="""
      The free tier shows banner and interstitial advertising served by
      <strong>Google AdMob</strong>, with consent collected through
      <strong>Google's User Messaging Platform</strong> (UMP) where the law requires it. Google and
      its partners may process your advertising ID, IP address and device information to serve and
      measure ads. Advertising has no access to your audio, your presets or your Bluetooth
      connections.
    """,
        consent=True,
        analytics=FB_FULL,
        analytics_note="""
      We use Google Analytics for Firebase to understand which features are used, Crashlytics to
      receive crash and error reports, Performance Monitoring for startup and responsiveness, Remote
      Config to change feature switches without an app update, and Cloud Messaging to send push
      notifications if you allow them. Analytics events describe app behaviour (for example
      &ldquo;preset saved&rdquo;); they never include your audio, and they do not identify you by
      name. You can turn notifications off in Android settings at any time.
    """,
        monetisation="""
      Bluetooth Mic is free to download and supported by advertising. An optional premium unlock is
      sold through Google Play Billing.
    """,
        products=[
            "<code>pamic_premium</code> &mdash; the premium product the app requests from Google Play",
        ],
        plans_note="""
      The app requests one premium product from Google Play. Google Play is the merchant of record,
      and the purchase sheet Play shows you states whether the product is a subscription or a
      one-time purchase, together with its price. <strong>Rely on that screen</strong>, not on any
      price written anywhere else.
    """,
        ads_terms="""
      The free version contains banner and interstitial advertising served by Google AdMob. Buying
      premium removes advertising. Advertising consent is collected through Google's User Messaging
      Platform where the law requires it.
    """,
        disclaimers=[
            "**Your audio is not recorded.** The app routes audio in real time; it does not record, store or upload it. You are responsible for what you transmit or amplify, and for having the permission of anyone whose voice is picked up.",
            "**Volume and hearing.** Amplifying live audio can produce very high sound levels, and prolonged exposure to loud sound can damage hearing. You control the gain and the output device: set safe levels, and take breaks.",
            "**Feedback and interference.** Routing a microphone to a loudspeaker can cause acoustic feedback, and Bluetooth audio can suffer interference and latency. Do not rely on this app where audio quality or timing is safety-critical.",
            "**Do not use the app while driving**, or in any other situation where operating a phone is unsafe or unlawful.",
        ],
        not_stored="""
      We do not sell your data. Audio is <strong>never recorded and never uploaded</strong>: there is
      no audio file, no recording history and no server-side audio. In this release your presets do
      not leave the phone either &mdash; the cloud backup that would carry them is switched off.
    """,
        play_answers=CLOUD_OFF_ANSWERS + [
            "Data collected: <strong>audio is not collected</strong> (real-time routing only); app activity, diagnostics and device identifiers may be collected; no account data is collected, because there is no account.",
        ],
    ),
    app(
        slug="pass-gen",
        name="Pass Gen",
        package="com.luckytools.pass_gen",
        theme="#a78bfa",
        footer_note="Password generator — you are responsible for how you store what it creates.",
        cloud=CLOUD_OPTIN_E2E,
        cloud_note="""
      Pass Gen generates passwords <strong>on your device</strong>. There is no Pass Gen vault in the
      cloud and no sign-in required. An <strong>optional, off-by-default encrypted backup</strong> is
      available if you want your settings and saved history to survive a lost phone: it is encrypted
      on your device before upload, so the server holds a blob it cannot read. Authentication and
      storage for that backup are handled by Supabase (our processor, EU servers, eu-west-2).
    """,
        cloud_terms="""
      <li>The backup is <strong>off by default</strong> and the app is fully usable without it.</li>
      <li>Anything in a backup is encrypted on your device before upload. The server cannot read it,
        and neither can we.</li>
      <li>A forgotten backup password cannot be recovered by us or by anyone else, and the backup
        cannot be decrypted without it. There is no master key, no recovery code and no reset.</li>
      <li>You may delete the backup account and its encrypted blob at any time &mdash; see the
        <a href="delete-data.html">data deletion</a> page. Verified deletions are completed within
        30 days.</li>
    """,
        cloud_delete="""
        <strong>Delete an optional cloud backup account (only if you created one)</strong><br />
        Open the app &rarr; <strong>Settings &rarr; Cloud backup &rarr; Delete account</strong> and
        type DELETE to confirm, or email
        <a href="mailto:support@cloudyni.com?subject=Pass%20Gen%20account%20deletion">support@cloudyni.com</a>
        with the subject &ldquo;Pass Gen account deletion&rdquo; from the address you signed up with.
        Either route removes the account and its encrypted blob, and we send one short confirmation
        reply when it is done.
    """,
        services=["None — the app requests no dangerous Android permissions"],
        collected=[
            "**Generated passwords and passphrases, and your saved history.** These are created on your device and stay on your device. They are never transmitted to us and we cannot see them.",
            "**Settings.** Length, character classes, word-list and separator preferences, theme and the app-lock setting.",
            "**An optional account email**, only if you create a cloud backup account.",
            "**Diagnostics and analytics** described in the analytics section below.",
            "**Advertising data** processed by Google AdMob on the free tier.",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Generated passwords and passphrases you choose to keep in History.",
            "Your generation settings, word lists and theme.",
            "The locally cached Premium entitlement for this install.",
        ],
        ads="""
      The free tier shows advertising served by <strong>Google AdMob</strong>. Google and its partners
      may process your advertising ID, IP address and device information to serve and measure ads.
      Where the law in your region requires consent before personalised advertising, that request is
      made before personalised ads are served. You can reset or delete your advertising ID in
      Android settings at any time. Advertising has no access to the passwords you generate.
    """,
        analytics=FB_FULL,
        analytics_note="""
      We use Google Analytics for Firebase for anonymous usage analytics, Crashlytics for crash and
      error reports, Performance Monitoring, Remote Config for feature switches, and Cloud Messaging
      for push notifications if you allow them. Analytics events describe app behaviour (for example
      &ldquo;password copied&rdquo;); they never contain a generated password, a passphrase or your
      History, and they do not identify you by name. You can turn notifications off in Android
      settings at any time.
    """,
        monetisation="""
      Core generation is free and supported by advertising. Optional Premium is a
      <strong>monthly auto-renewing subscription</strong> sold through Google Play Billing. It
      removes advertising and unlocks the extra options listed on the app's Google Play listing.
    """,
        products=[
            "<code>pass_gen_premium_monthly</code> &mdash; monthly auto-renewing subscription",
        ],
        plans_note="""
      Premium is a subscription: it renews each month until you cancel, and there is no one-time or
      lifetime option for this app.
    """,
        ads_terms="""
      The free version contains advertising served by Google AdMob. An active Premium subscription
      removes advertising for the period you have paid for.
    """,
        disclaimers=[
            "**What the app is.** Pass Gen generates passwords and passphrases on your device. It is not a password manager, a cloud vault, a breach monitor or a security audit service, and it does not store anything for you beyond the History you keep on the device.",
            "**You are responsible for storage.** We never receive your generated passwords, so we cannot recover, resend or reset one. If you lose your device, or lose the backup password for an optional encrypted backup, that data is gone.",
            "**Strength is not a guarantee.** A long random password reduces risk; it does not prevent every attack. Keep your device locked and updated, and never reuse a password across important accounts.",
            "**No warranty of fitness.** We do not warrant that a generated value will satisfy every third-party site's password rules, or that the app will be uninterrupted or error-free.",
        ],
        not_stored="""
      Generated passwords, passphrases and your History are created and kept on your device. We cannot
      read them, and there is no Pass Gen vault on our servers to read them from. Leaving the default
      cloud backup switched off means nothing from this app ever reaches a server of ours.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>yes</strong> (optional encrypted backup only; the app is fully usable signed out).",
            "Account creation is <strong>not required</strong> to use the app.",
            "Users can request deletion &mdash; <strong>yes</strong> (in-app, by email, or by clearing app storage / uninstalling; this page is the deletion URL).",
            "Deletion requests are completed within <strong>30 days</strong>.",
            "Data collected: generated passwords are <strong>not</strong> collected; app activity, diagnostics and device identifiers may be collected; the optional account email is collected.",
        ],
    ),
    app(
        slug="factswipe",
        name="FactSwipe",
        package="com.luckytools.facts_kids",
        theme="#5C6BC0",
        footer_note="Facts and trivia for fun — check anything important against a primary source.",
        cloud=CLOUD_GATED_OFF,
        cloud_note=CLOUD_OFF_NOTE,
        services=["None — the app requests no dangerous Android permissions"],
        collected=[
            "**Your progress and favourites.** Saved facts, favourites, quiz scores, streaks and the cards you have already seen are stored on your device so the app can carry on where you left off.",
            "**Settings.** Theme, sound and notification preferences for the app.",
            "**Advertising data** processed by Google AdMob on the free tier, in child-directed mode (see the advertising section).",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Saved facts and favourites.",
            "Quiz scores, streaks and progress through each deck.",
            "App settings, including the chosen theme and sound preference.",
            "The locally cached ad-free entitlement for this install.",
        ],
        ads="""
      The free version shows advertising served by <strong>Google AdMob</strong>. FactSwipe is set
      up for a young audience, so it flags itself as child-directed: ads are requested in a
      non-personalised, limited mode, are restricted to content rated for general audiences, and
      your advertising ID is not used to build an interest profile or to personalise advertising for
      you. Where the law in your region requires consent, that request is made before ads are
      served. You can reset or delete your advertising ID in Android settings. Advertising has no
      access to your saved facts or your progress.
    """,
        children="""
      FactSwipe is made for families and children as well as adults. It is designed so that it can be
      used by a child without an account: <strong>there is no sign-in, no profile, no chat, no
      user-generated content, no location collection, no contacts access and no in-app purchases
      that can be triggered by accident</strong> beyond what Google Play itself requires. We do not
      knowingly collect personal information from children, and because the app has no account there
      is no child profile on our servers. Where advertising is shown it is requested as
      child-directed and non-personalised, and the AdMob content rating limits what can appear. If a
      parent or guardian believes a child has sent us personal information (for example by emailing
      support), contact <a href="mailto:support@cloudyni.com">support@cloudyni.com</a> and we will
      delete that correspondence.
    """,
        analytics=[],
        analytics_note="""
      FactSwipe does not use Google Analytics, Firebase or any other third-party analytics or crash
      reporting service. Nothing about how you use the app leaves your device; there is no
      behavioural profile and no usage log on our side.
    """,
        retention="""
      Facts, favourites, scores and settings stay on your device until you clear the app's storage or
      uninstall it. Because there is no account and no server copy, we hold nothing to expire.
      Support correspondence is kept only as long as needed to resolve the query.
    """,
        monetisation="""
      FactSwipe is free to download and supported by advertising. An optional premium product sold
      through Google Play Billing removes advertising and unlocks the extra features described on the
      app's Google Play listing.
    """,
        products=[
            "<code>facts_kids_premium_monthly</code> &mdash; the premium product the app requests from Google Play",
        ],
        plans_note="""
      The identifier names a monthly product, so treat it as an auto-renewing subscription that
      continues until you cancel. We do not sell a separate lifetime unlock for this app, and the
      Google Play purchase sheet &mdash; not this page or any marketing page &mdash; states the
      final price and whether a product renews.
    """,
        ads_terms="""
      The free version contains advertising served by Google AdMob in child-directed,
      non-personalised mode. Buying the premium product removes advertising for the period you have
      paid for. We do not show ads inside any paid feature.
    """,
        disclaimers=[
            "**Facts are for entertainment.** The app presents trivia and general facts. Some are simplified, and some depend on how a question is framed or on a source that may since have been revised. Verify anything that matters against a primary source.",
            "**Not professional advice.** Nothing in the app is health, medical, legal, financial, safety or educational advice, and it is not a study programme, revision service or assessment.",
            "**Third-party content.** Some cards reference public facts and figures drawn from third-party sources. We do not claim ownership of those underlying facts and we cannot warrant that every card is free of error.",
        ],
        not_stored="""
      We do not sell your data and we do not build an advertising profile of you. There is no account,
      no cloud backup and no server copy of your progress &mdash; Favourites, scores, streaks and
      settings exist only on your device, and removing the app removes them.
    """,
        play_answers=CLOUD_OFF_ANSWERS + [
            "Data collected: progress, favourites and settings are stored on the device and are <strong>not</strong> collected by us; device identifiers may be processed by Google AdMob to serve non-personalised, child-directed ads.",
        ],
    ),
    app(
        slug="religious-reader",
        name="Religious Reader",
        package="com.luckytools.bible_buddy",
        theme="#4A6FA5",
        favicon="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 100 100'%3E%3Crect fill='%234A6FA5' rx='22' width='100' height='100'/%3E%3Ctext x='50' y='64' text-anchor='middle' font-size='42'%3E%E2%9C%A8%3C/text%3E%3C/svg%3E",
        footer_note="Scripture texts for reading and study — not a substitute for your own tradition or a religious authority.",
        cloud=CLOUD_NONE,
        cloud_note="""
      <p>
        Religious Reader has <strong>no account, no sign-in and no cloud service</strong>. The texts
        are bundled with the app and everything you save stays in the app's storage on your device.
        Nothing you read, highlight or note is uploaded to us: there is no server-side copy of your
        data to read, export or delete.
      </p>
      <p>
        The app also contains <strong>no third-party analytics or crash-reporting SDK</strong>. The
        only outbound connections it makes are the ad requests described below and ordinary Google
        Play traffic.
      </p>
    """,
        services=["None — the app requests no dangerous Android permissions"],
        collected=[
            "**Highlights, notes and bookmarks.** Verse highlights, personal notes, bookmarks and reading-position markers are stored on your device.",
            "**Reading progress.** Streaks, chapters read and the texts you have opened, kept so the app can resume where you left off.",
            "**Settings.** Theme, font size, preferred translation or text selection and notification preferences.",
            "**Advertising data** processed by Google AdMob on the free tier (see the advertising section).",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your highlights, notes and bookmarks.",
            "Reading progress and streaks.",
            "Chosen translation or text, plus display settings.",
            "The locally cached ad-free entitlement for this install.",
        ],
        ads="""
      The free version shows advertising served by <strong>Google AdMob</strong>, and where the law
      requires consent it is collected through <strong>Google's User Messaging Platform</strong>
      before personalised advertising is served. Google and its partners may process your advertising
      ID, IP address and device information to serve and measure ads. You can reset or delete your
      advertising ID and change your ad settings in Android. Advertising never sees your notes, your
      highlights or which verses you read.
    """,
        consent=True,
        children="""
      Religious Reader is suitable for all ages and is used by families, including children. It needs
      no account and creates no profile, so we collect no personal information from a child: there is
      nothing to sign up for and nothing sent to us. Where ads are shown we restrict them as the law
      and Google Play's Families requirements demand, and a parent or guardian can remove ads with
      the premium product bought through Google Play. If you believe a child has sent us personal
      information (for example by emailing support), contact
      <a href="mailto:support@cloudyni.com">support@cloudyni.com</a> and we will delete it.
    """,
        analytics=[],
        analytics_note="""
      Religious Reader contains no Google Analytics, no Firebase and no third-party crash-reporting
      SDK. Nothing about your reading behaviour is measured or transmitted, and there is no usage log
      on our side.
    """,
        retention="""
      Highlights, notes, bookmarks, streaks and settings remain on your device until you clear the
      app's storage or uninstall it; we hold no copy. Support correspondence is kept only as long as
      needed to answer the query.
    """,
        monetisation="""
      Religious Reader is free to download and supported by advertising. An optional premium product
      sold through Google Play Billing removes advertising and unlocks the additional reading
      features described on the app's Google Play listing.
    """,
        products=[
            "<code>religious_reader_premium_monthly</code> &mdash; the premium product the app requests from Google Play",
        ],
        plans_note="""
      The identifier names a monthly product, so treat it as an auto-renewing subscription. Whether a
      product renews, and what it costs, is determined by the Google Play purchase sheet shown before
      you confirm &mdash; that sheet is authoritative, not this page or any marketing page. We do not
      sell a separate lifetime unlock for this app.
    """,
        ads_terms="""
      The free version contains advertising served by Google AdMob, with consent collected through
      Google's User Messaging Platform where required. Buying the premium product removes
      advertising for the period you have paid for.
    """,
        disclaimers=[
            "**Texts are third-party material.** Scripture texts and translations are supplied by third-party publishers and made available offline in the app. Copyright in a translation belongs to its publisher, and we do not claim otherwise.",
            "**Translations differ.** Wording, versification and even the number of books vary between traditions and editions. If a passage matters to you, compare it with the printed edition your community uses.",
            "**Not a religious authority.** The app is a reading tool. It does not provide interpretation, rulings, pastoral care, liturgical guidance or any form of religious or professional advice.",
            "**No endorsement.** No church, mosque, synagogue, temple, religious body or publisher endorses, sponsors or authorises this app unless stated on our own pages.",
            "**Verification.** We work to keep bundled texts faithful to their published source, but we cannot warrant that an offline copy is free of typographical or transcription error.",
        ],
        not_stored="""
      We do not sell your data and we do not build a profile of what you read, highlight or pray.
      There is no account and no cloud backup, so your notes and reading history never reach a server
      of ours at all &mdash; they exist only on your device.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>no</strong>. The app has no sign-in and no server-side profile.",
            "Account creation is <strong>not required</strong> and is not available.",
            "Users can request deletion &mdash; <strong>yes</strong> (clearing app storage or uninstalling removes every highlight, note and setting at once; this page is the deletion URL).",
            "Deletion requests are completed within <strong>30 days</strong>.",
            "Data collected: highlights, notes, bookmarks and reading progress are stored on the device and are <strong>not</strong> collected by us; device identifiers and ad interaction data may be processed by Google AdMob to serve ads.",
        ],
    ),
    app(
        slug="daily-affirmation",
        name="Daily Affirmation",
        package="com.dailyaffirmation.app",
        theme="#4a7c6a",
        footer_note="Wellbeing and reflection tool — not medical, psychological or crisis advice.",
        cloud=CLOUD_OPTIN_E2E,
        cloud_note="""
      <p>
        Cloud backup is <strong>optional and off by default</strong>. The app is fully usable signed
        out, and everything works with no account at all. If you choose to create one, a copy of your
        favourites, history, mood check-ins and settings is encrypted on your device before it is
        uploaded, so the server stores a blob it cannot read. Authentication and storage are handled
        by Supabase (our processor, servers in the EU, eu-west-2).
      </p>
      <p>
        There is no advertising profile behind the account and no selling of data. The account exists
        only so that your own content can be restored to a new device.
      </p>
    """,
        cloud_terms="""
      <li>Your content is encrypted on your device before upload. The server cannot read it, and
        neither can we.</li>
      <li>A forgotten backup password cannot be recovered by us and the backup cannot be decrypted
        without it. There is no master key or reset. Keep your own copy of anything you cannot afford
        to lose.</li>
      <li>You may delete the account and the encrypted blob at any time &mdash; see the
        <a href="delete-data.html">data deletion</a> page. We complete verified deletions within 30
        days.</li>
    """,
        cloud_delete="""
        <strong>Delete an account or a backup (only if you created one)</strong><br />
        In the app open <strong>Settings &rarr; Cloud backup</strong> and choose either
        <strong>Delete account</strong> (removes the account and the encrypted backup) or
        <strong>Delete backup</strong> (keeps the account, erases the stored copy). You can also email
        <a href="mailto:support@cloudyni.com?subject=Daily%20Affirmation%20account%20deletion">support@cloudyni.com</a>
        with the subject &ldquo;Daily Affirmation account deletion&rdquo; from the address you signed
        up with, and we will delete it and confirm in a short reply.
    """,
        services=["Notifications"],
        collected=[
            "**Your favourites and history.** The affirmations you save, and which ones you have seen, are stored on your device so the app can continue where you left off.",
            "**Mood check-ins.** If you record a mood, that entry and its date are stored on your device. It is your own private log: it is not used for advertising, not used to profile you, and not shared with anyone.",
            "**Settings.** Theme, reminder times, notification preferences, text size and the optional app lock or PIN.",
            "**An optional account email**, only if you choose to switch on encrypted cloud backup.",
            "**Purchase verification.** When you buy or restore Premium the app asks a verification service that we run ourselves to confirm the purchase with Google. That request carries the Google Play purchase token, the product or subscription identifier and the app package name &mdash; and, if Play Integrity checking is switched on, an app-integrity token. It never carries your email, your favourites, your history or your mood entries. The service asks Google for a verdict and keeps no database of its own.",
            "**Diagnostics and analytics** described in the analytics section below.",
            "**Advertising data** processed by Google AdMob on the free tier.",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your favourite affirmations and your reading history.",
            "Mood check-ins and any notes you attach to them.",
            "Reminder schedule, theme, text size and app-lock settings.",
            "The locally cached premium entitlement for this install.",
        ],
        sensitive="""
      <p>
        Mood check-ins and any notes you write can say something about your wellbeing, so we treat
        them as the most sensitive thing in the app. They are written to your device's private
        storage, are excluded from advertising and from analytics events, and are never used to build
        a profile of you. They reach a server only if you deliberately create an account and leave
        cloud backup switched on, and even then only as a blob encrypted with your password that we
        cannot read.
      </p>
      <p>
        We do not sell this data, we do not share it with advertisers or data brokers, and we do not
        use it for research. You can erase it at any time from inside the app.
      </p>
    """,
        ads="""
      The free version shows advertising served by <strong>Google AdMob</strong>, with consent
      collected through <strong>Google's User Messaging Platform</strong> where the law requires it.
      Google and its partners may process your advertising ID, IP address and device information to
      serve and measure ads. Your mood check-ins, favourites and history are never passed to AdMob or
      to any advertiser, and advertising is never targeted at how you are feeling.
    """,
        consent=True,
        children="""
      Daily Affirmation is aimed at a general adult audience and is not directed at children. We do
      not knowingly collect personal information from a child. Because the app can be installed on a
      shared device, a parent or guardian may contact
      <a href="mailto:support@cloudyni.com">support@cloudyni.com</a> to have any correspondence
      deleted, and clearing the app's storage or uninstalling it removes everything held locally for
      that install.
    """,
        analytics=FB_FULL,
        analytics_note="""
      We use <strong>Google Analytics for Firebase</strong> (GA4) for anonymous usage analytics,
      <strong>Crashlytics</strong> for crash and error reports, <strong>Firebase Performance
      Monitoring</strong> for startup and responsiveness, <strong>Remote Config</strong> to change
      feature switches without an app update, and <strong>Firebase Cloud Messaging</strong> for
      reminder notifications if you allow them. Analytics events describe app behaviour (for example
      &ldquo;affirmation opened&rdquo;); they never contain the text you write in a mood check-in or a
      note, and they do not identify you by name. You can turn notifications off in Android settings
      at any time.
    """,
        retention="""
      Affirmations, favourites, history and mood check-ins stay on your device until you clear the
      app's storage or uninstall it. If you create an account, the encrypted backup is kept until you
      delete the backup or the account from inside the app, after which it is removed from our
      processor's storage. Deletion requests made by email are completed within 30 days, and
      aggregated, non-identifying analytics are retained by Google under our Firebase configuration.
      A Play purchase token sent for entitlement verification is used only to answer that one request
      and is not written to a database by our verification service; Google keeps the underlying Play
      purchase record under its own policies. Support correspondence is kept only as long as needed to
      answer the query.
    """,
        monetisation="""
      Daily Affirmation is free to download and supported by advertising. Optional Premium is an
      <strong>auto-renewing subscription</strong> sold through Google Play Billing; it removes
      advertising and unlocks the extra personalisation features described on the app's Google Play
      listing.
    """,
        products=[
            "<code>premium_monthly</code> &mdash; monthly auto-renewing subscription",
            "<code>premium_colors</code> &mdash; a legacy one-time unlock that is <strong>no longer sold</strong>; it can still be restored if you bought it",
        ],
        plans_note="""
      Premium is a subscription: it renews each month until you cancel in Google Play. The only
      one-time product this app ever sold was the legacy colour pack, which is withdrawn from sale
      &mdash; it remains valid for customers who already own it, and reinstall-and-restore brings it
      back. Google Play's purchase sheet, not this page, states the price and whether something
      renews.
    """,
        ads_terms="""
      The free version contains advertising served by Google AdMob, with consent collected through
      Google's User Messaging Platform where required. An active Premium subscription removes
      advertising for the period you have paid for.
    """,
        disclaimers=[
            "**Not medical or psychological advice.** Daily Affirmation offers affirmations, prompts and reflection for general wellbeing. It is not therapy, counselling, diagnosis or treatment, and it is not a substitute for care from a qualified professional.",
            "**No crisis support.** The app cannot help in an emergency. If you are in crisis or thinking about harming yourself, contact your local emergency number or a crisis line in your country immediately, and speak to a healthcare professional.",
            "**Your judgement comes first.** Reflection prompts are general and may not suit your circumstances. Ignore anything that does not fit, and stop using the app if it makes you feel worse rather than better.",
            "**Mood check-ins are your own record.** They are a self-reported log, not a clinical measurement or an assessment of your mental health, and they must not be relied on for any medical purpose.",
        ],
        not_stored="""
      We do not sell your data and we do not use what you write to target advertising. Your mood
      check-ins, notes and favourites are private to your device unless you deliberately switch on the
      optional encrypted backup. There is no shadow profile, no social feed and no sharing with other
      users &mdash; nothing in this app is public.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>yes</strong> (optional encrypted backup only; the app is fully usable signed out and the backup is off by default).",
            "Account creation is <strong>not required</strong> to use the app.",
            "Users can request deletion &mdash; <strong>yes</strong> (in-app Settings &rarr; Cloud backup &rarr; Delete account or Delete backup, by email, or by clearing app storage / uninstalling; this page is the deletion URL).",
            "Deletion requests are completed within <strong>30 days</strong>.",
            "Data collected: favourites, history and mood check-ins are stored <strong>on the device</strong> and are not collected by us unless you enable backup; app activity, diagnostics and device identifiers may be collected; the optional account email is collected.",
        ],
    ),
    app(
        slug="perimenopause-tracker",
        name="PeriLog",
        package="com.luckytools.perimenopause_tracker",
        theme="#5F7A67",
        favicon="assets/icon.png",
        footer_note="Health and wellbeing tracker — not medical advice, not a contraceptive and not a diagnostic device.",
        cloud=CLOUD_OPTIN_E2E,
        cloud_note="""
      <p>
        Cloud backup is <strong>optional and off by default</strong>. PeriLog is complete without an
        account &mdash; every feature works with your data on the phone. If you choose
        <strong>Settings &rarr; Cloud backup &amp; sync</strong> and create an account, your logs are
        encrypted <strong>on your device</strong> with AES-256-GCM using a key derived from your
        password (PBKDF2-HMAC-SHA256, 120,000 iterations). Only that ciphertext leaves the phone:
        your account holds one encrypted backup record, and the key stays in this device's secure
        storage. Authentication and storage are provided by <strong>Supabase</strong>, our processor,
        with the project hosted in the <strong>United Kingdom (London, eu-west-2)</strong>.
      </p>
      <p>
        Because your password is what decrypts the backup, <strong>we cannot read it, we cannot
        recover it for you, and a password reset cannot unlock an older backup</strong>. Signing in on
        another device with the same email and password restores the same encrypted data. Signing out
        removes the local key. One encrypted row per account is all that exists server-side &mdash;
        there is no readable copy, no analytics copy and no second database.
      </p>
    """,
        cloud_terms="""
      <li>Your logs are encrypted on your device before upload. The server stores ciphertext it cannot
        read, and so can we.</li>
      <li>A forgotten backup password cannot be recovered by us and the backup cannot be decrypted
        without it. There is no master key and no reset. Do not treat cloud backup as your only copy of
        anything you cannot afford to lose.</li>
      <li>The backup is a convenience, not a medical record. Do not rely on it for clinical purposes,
        and keep your own exports (the app can write a JSON backup file or a PDF report) if the data
        matters to you.</li>
      <li>You may delete the account and its encrypted backup at any time &mdash; from inside the app
        or by asking us. We complete verified deletions within 30 days.</li>
    """,
        cloud_delete="""
        <strong>Delete a cloud backup account (only if you created one)</strong><br />
        In the app open <strong>Settings &rarr; Cloud backup &amp; sync</strong> and tap
        <strong>Delete account and cloud data</strong>, then confirm. That permanently removes the
        account and the encrypted backup; data on the phone is untouched. The same screen offers
        <strong>Sign out of cloud backup</strong> if you only want to stop syncing &mdash; signing out
        deletes the local encryption key, which makes the remote backup unrestorable from this device.
        You can also email
        <a href="mailto:support@cloudyni.com?subject=PeriLog%20account%20deletion">support@cloudyni.com</a>
        with the subject &ldquo;PeriLog account deletion&rdquo; from the address you signed up with and
        we will delete the account and confirm in a short reply.
    """,
        services=[
            "Notifications and scheduled reminders, only if you switch a reminder on",
            "Run at start-up, so a reminder you set still fires after a restart",
            "Vibration, for reminder alerts",
            "Internet access, for free-tier advertising, Google Play purchases and the optional cloud backup",
            "None for your body or your photos &mdash; the app requests no location, camera, microphone, contacts, phone or storage permission",
        ],
        collected=[
            "**Cycle and symptom entries you record.** Periods, flow, symptoms, mood, sleep, energy, medication and the rest are written to the app's private database on your device. They are not sent to us and we cannot see them unless you deliberately create an account and leave cloud backup switched on.",
            "**Photo journal entries.** A journal entry stores the path of a photo already on your device, which the screen copies into the app's own private folder, plus any caption and tags you add. The app asks for no camera or gallery permission, and the picture itself is not uploaded.",
            "**Goals and notes.** Anything you type into a goal or note stays in the same local database.",
            "**Settings and reminders.** Theme, cycle-length defaults, reminder times, text size and the optional app lock.",
            "**An optional account email**, only if you choose to create a cloud backup account.",
            "**Advertising data** processed by Google AdMob on the free tier (see the advertising section).",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your cycle, symptom, mood, sleep, medication and goal entries.",
            "Photo journal entries, including the app's own copy of each picture.",
            "Reminder schedule, theme, text size and the optional app lock.",
            "Any JSON backup or PDF report you export, until you delete the file.",
            "The locally cached Premium entitlement for this install.",
        ],
        sensitive="""
      <p>
        PeriLog exists to record information about your body and your health, so nearly everything in
        it is the most sensitive category of personal data. We treat it that way: it is written to your
        device's private storage, it is excluded from analytics, and it is not used to build a profile of
        you, to target advertising or to train anything.
      </p>
      <p>
        We do not sell it and we do not share it with advertisers, insurers, employers or data brokers.
        It reaches a server only if you deliberately create a cloud backup account, and even then only
        as a blob encrypted with your password that we cannot read. You can erase it at any time from
        inside the app.
      </p>
    """,
        ads="""
      The free version shows banner and interstitial advertising served by <strong>Google AdMob</strong>,
      with consent collected through <strong>Google's User Messaging Platform</strong> where the law
      requires it. Google and its partners may process your advertising ID, IP address and device
      information to serve and measure ads. The app requests <strong>no location permission</strong>,
      and no entry you make &mdash; cycle, symptom, mood or photo &mdash; is ever passed to AdMob or to
      any advertiser. An active Premium subscription removes advertising entirely.
    """,
        consent=True,
        children="""
      PeriLog is designed for adults tracking perimenopause and menstrual health, and it is not directed
      at children. We do not knowingly collect personal information from a child. If a child has used
      the app on a shared device, clearing the app's storage or uninstalling it removes everything held
      locally, and you can contact
      <a href="mailto:support@cloudyni.com">support@cloudyni.com</a> about any account or support email.
    """,
        analytics=[],
        analytics_note="""
      This app contains <strong>no third-party analytics or crash-reporting SDK</strong>. Nobody
      receives a record of how you use it, there is no session recording and there is no crash
      telemetry, so a crash stays on your phone &mdash; which also means we cannot see it unless you
      tell us. The only outside software in the app is Google's: AdMob for the ads on the free tier and
      Play Billing for purchases. Google Play itself collects install and payment information under
      Google's own privacy policy.
    """,
        retention="""
      Your entries stay on your device until you delete them, clear the app's storage or uninstall the
      app. If you create an account, the encrypted backup is kept until you delete it or delete the
      account from inside the app, after which the record is removed from our processor's storage.
      Deletion requests sent by email are completed within 30 days. Support correspondence is kept only
      as long as needed to answer the query. Google keeps purchase records as merchant of record, and
      the advertising identifiers held by Google are governed by Google's retention rules, not ours.
    """,
        monetisation="""
      PeriLog is free to download and supported by advertising. Optional Premium is sold through Google
      Play Billing as <strong>an auto-renewing monthly subscription</strong>, alongside
      <strong>a one-time lifetime purchase</strong> that does not renew.
    """,
        products=[
            "<code>premium_monthly</code> &mdash; auto-renewing monthly subscription",
            "<code>premium_lifetime</code> &mdash; one-time purchase, no renewal",
        ],
        plans_note="""
      Premium removes advertising and extends trend history to the full 90-day view. Two products are
      offered: a monthly subscription that renews until you cancel, and a lifetime purchase that is paid
      once and never renews. The Google Play purchase sheet &mdash; not this page and not any marketing
      page &mdash; states the price, the billing period and whether the product renews.
    """,
        ads_terms="""
      The free version contains banner and interstitial advertising served by Google AdMob, with consent
      collected through Google's User Messaging Platform where required. Premium removes advertising for
      the period you have paid for &mdash; permanently, in the case of the lifetime product.
    """,
        disclaimers=[
            "**Not medical advice and not a medical device.** PeriLog is a self-tracking notebook. It does not diagnose, treat, cure or prevent any condition, it is not a contraceptive, and it cannot tell you whether you are fertile, pregnant or menopausal.",
            "**Predictions are estimates, not facts.** Cycle and symptom predictions are calculated from the dates you enter. They can be wrong, and they are not a substitute for clinical assessment, diagnosis or testing.",
            "**No emergency use.** The app has no alarm, no monitoring and nobody watching the data. In an emergency, contact your local emergency number.",
            "**You decide what to record.** Only log what helps you. You are in control of what you write down, and everything can be deleted from the app.",
            "**Do not rely on cloud backup for anything critical.** Because the backup is encrypted with your password, a lost password means a lost backup, and we cannot restore it for you.",
        ],
        not_stored="""
      We do not sell your data, we do not use your health entries to target advertising, and we hold no
      readable copy of them. Without a cloud backup account, your cycle and symptom history exists only
      on your phone, and we have nothing on a server to read, export or delete. There is no social
      feature, no clinical register and no sharing with anyone.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>yes</strong> (an optional, end-to-end encrypted cloud backup; the app is fully usable signed out and backup is off by default).",
            "Account creation is <strong>not required</strong> to use the app.",
            "Users can request deletion &mdash; <strong>yes</strong> (in-app Settings &rarr; Cloud backup &amp; sync &rarr; Delete account and cloud data, by email, or by clearing app storage / uninstalling; this page is the deletion URL).",
            "Deletion requests are completed within <strong>30 days</strong>.",
            "Data collected: cycle, symptom, mood and photo-journal entries are stored <strong>on the device</strong> and are not collected by us unless you enable encrypted backup; the optional account email is collected; app activity, diagnostics and device identifiers may be collected by Google's advertising SDK.",
        ],


    ),
    app(
        slug="pantry-pals",
        name="Pantry Pals",
        package="com.luckytools.fridge_split",
        theme="#8B6F47",
        footer_note="Household food-sharing and pantry tracker — nutrition figures are estimates, not dietary advice.",
        cloud=CLOUD_LIVE_SYNC,
        cloud_note="""
      <p>
        Pantry Pals works fully offline and unsigned-in: items, history, profiles and preferences live
        in a local database on your phone. An account and <strong>live sync</strong> are
        <strong>optional and off until you switch them on</strong>. If you do, the pantry content you
        see in the app is also stored by our processor <strong>Supabase</strong>, in the
        <strong>United Kingdom (London, eu-west-2)</strong>, so every phone in your household can show
        the same fridge.
      </p>
      <p>
        Sign-in is by email and password, or with Google if you prefer. You join a household with an
        invite code or link rather than by browsing, and access on the server is restricted per
        household, so a member of one household cannot read another's pantry. Synced rows are
        <strong>not end-to-end encrypted</strong> &mdash; the service can read them, because that is
        what makes sharing work, and the same data appears on every member's phone. Treat a shared
        pantry as shared information: do not put anything in it you would not show the other members,
        and keep medical details out of the notes.
      </p>
    """,
        cloud_terms="""
      <li>Live sync is a shared-household feature, not private storage. Anything you add to a synced
        pantry is visible to the other members of that household and is stored on a server we can read.</li>
      <li>You need a working email address to create an account, and you must keep your password (or
        your Google account) secure. Everything done under your account in a shared pantry is attributed
        to your display name.</li>
      <li>Photos you attach to a synced item are uploaded to our storage bucket and served to household
        members through short-lived signed links. Removing the item, leaving the household or deleting
        the account removes the app's copy; signed links already issued expire shortly afterwards.</li>
      <li>We may suspend or delete an account that is used to abuse the service or to store unlawful
        content, and we may stop offering live sync altogether.</li>
      <li>Keep your own copy of anything you cannot afford to lose &mdash; the app can export your data,
        and sync is a convenience, not a backup guarantee.</li>
      <li>You may delete the account and its cloud copy at any time. See the
        <a href="delete-data.html">data deletion</a> page.</li>
    """,
        cloud_delete="""
        <strong>Delete an account and its cloud copy (only if you enabled live sync)</strong><br />
        In the app open <strong>More &rarr; Live sync</strong> and tap
        <strong>Delete account</strong>, then type <strong>DELETE</strong> to confirm. That removes the
        account, your profile and the synced pantry rows and photos it owns; the household's other
        members keep their own copies on their phones. Leaving just the household (rather than deleting
        the account) is a separate action on the same screen. You can also email
        <a href="mailto:support@cloudyni.com?subject=Pantry%20Pals%20account%20deletion">support@cloudyni.com</a>
        with the subject &ldquo;Pantry Pals account deletion&rdquo; from the address you signed up with
        and we will delete the account and confirm in a short reply.
    """,
        services=[
            "Camera, only while you are scanning a barcode &mdash; you can type the number in instead",
            "Microphone, only while you use voice entry for an item",
            "Notifications, for expiry, shopping and household alerts you turn on",
            "Run at start-up, so reminders you set still fire after a restart",
            "Network access, for advertising, purchases, barcode lookups, optional sync and push messaging",
            "Vibration, for alerts",
            "Your chosen photos, read only when you attach one to an item",
        ],
        collected=[
            "**Pantry content.** Item names, quantities, units, storage zones, use-by dates, sharing flags, consumption history and shopping-list entries, all stored locally and synced only if you enable live sync.",
            "**Item photos.** Pictures you attach with Android's own photo picker. They stay on the device in local-only use; with sync on they are uploaded so the rest of the household can see them.",
            "**Display name and household profiles.** The name shown next to what you add, plus any allergen or dietary notes a household profile carries. Those notes can be sensitive, so enter only what you need for the household's warnings.",
            "**Barcode lookups.** The number you scan or type, sent to OpenFoodFacts to fetch product details. No account, name or household identifier is sent with it.",
            "**An optional account email**, only if you create an account for live sync.",
            "**Notification token.** A device push token, stored only when you allow notifications, so household alerts can reach the right phone.",
            "**Diagnostics and analytics** described in the analytics section below.",
            "**Advertising data** processed by Google AdMob on the free tier.",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your pantry items, zones, quantities and use-by dates.",
            "Consumption history and your shopping list.",
            "Household member profiles and any allergen or dietary notes you entered.",
            "Item photos, held in the app's own storage.",
            "Reminder and notification preferences, theme and language settings.",
            "The locally cached Premium entitlement for this install.",
        ],
        sensitive="""
      <p>
        Allergen and dietary notes, and anything you write about a person's health, are the most
        sensitive information this app can hold. They are used only to raise a warning where the app
        thinks a product may conflict with a profile you set up, and you choose what to enter. You can
        edit or delete them at any time, and you can leave a profile blank.
      </p>
      <p>
        Because a synced pantry is shared with the other members of that household, those notes are
        visible to them &mdash; that is the point of the feature. If you would rather keep a condition
        private, keep it out of the shared profile and rely on your own judgement instead.
      </p>
    """,
        ads="""
      The free version shows advertising served by <strong>Google AdMob</strong>, with consent collected
      through <strong>Google's User Messaging Platform</strong> where the law requires it. Google and its
      partners may process your advertising ID, IP address and device information to serve and measure
      ads. Advertising never receives your pantry content, your household profiles or your photos, and
      we do not use what is in your fridge to target ads. Buying an ad-free or Kitchen Premium
      subscription removes advertising.
    """,
        consent=True,
        extra_processors=[
            (
                "OpenFoodFacts",
                "a community-maintained public product database. When you scan or type a barcode the "
                "number is sent to it, and the product name, ingredients, allergens and nutrition figures "
                "come back. No personal data, account or household identifier is included in the request. "
                "Its data is contributed by the public and may be incomplete or wrong &mdash; check the "
                "packet if a warning matters.",
            ),
            (
                "Google ML Kit",
                "used for on-device receipt text recognition. The receipt image is processed on your phone "
                "and is not uploaded to us or to Google by this feature.",
            ),
            (
                "Android speech recognition",
                "used when you dictate an item name. Audio is handled by the speech service on your device "
                "under its own terms, and it is never sent to us.",
            ),
        ],
        children="""
      Pantry Pals is a household shopping tool aimed at a general audience and is not directed at
      children. We do not knowingly collect personal information from a child. If a child has used the
      app on a shared device, clearing the app's storage or uninstalling it removes everything held
      locally, and a parent or guardian can contact
      <a href="mailto:support@cloudyni.com">support@cloudyni.com</a> about an account or a support email.
    """,
        analytics=FB_FULL,
        analytics_note="""
      We use <strong>Google Analytics for Firebase</strong> for anonymous usage analytics,
      <strong>Crashlytics</strong> for crash and error reports, <strong>Firebase Performance
      Monitoring</strong> for startup and responsiveness, <strong>Remote Config</strong> to change
      feature switches without an app update, and <strong>Firebase Cloud Messaging</strong> to deliver
      household push notifications when you allow them. Analytics events describe app behaviour (for
      example &ldquo;item added&rdquo;) and never include item names, notes, photos, household profiles
      or anything else you typed. You can turn notifications off in Android settings at any time.
    """,
        retention="""
      Local pantry data stays on your phone until you clear the app's storage or uninstall it. Synced
      data stays on our processor's storage while the account exists and while you are a member of a
      household: deleting the account removes the rows and photos it owns, and leaving a household
      removes your membership and your profile from it. Household changes are recorded in an audit log so
      members can see who changed what, and those entries are deleted with the household. Support
      correspondence is kept only as long as needed to answer the query, and deleted on request within
      90 days. Firebase and AdMob data is retained by Google under our configuration and Google's own
      rules, and Google keeps purchase records as merchant of record.
    """,
        monetisation="""
      Pantry Pals is free to download and supported by advertising. Two optional premium tiers are sold
      through Google Play Billing, each as an <strong>auto-renewing subscription</strong> (monthly or
      yearly).
    """,
        products=[
            "<code>pantry_pals_adfree_monthly</code> &mdash; monthly auto-renewing subscription",
            "<code>pantry_pals_adfree_yearly</code> &mdash; yearly auto-renewing subscription",
            "<code>pantry_pals_kitchen_monthly</code> &mdash; monthly auto-renewing subscription (Kitchen Premium)",
            "<code>pantry_pals_kitchen_yearly</code> &mdash; yearly auto-renewing subscription (Kitchen Premium)",
            "<code>fridge_share_premium_monthly</code> &mdash; a <strong>legacy</strong> product that is no longer offered; existing subscribers keep their entitlement",
        ],
        plans_note="""
      <strong>Ad-Free</strong> removes advertising on the phone that bought it. <strong>Kitchen
      Premium</strong> raises the free-tier cap of 15 items per kitchen to unlimited for everyone in
      that household &mdash; one person pays and all members benefit &mdash; and it also removes
      advertising for the subscriber. All four current products are subscriptions and renew at the price
      Google Play shows until you cancel; we do not sell a lifetime unlock. The Google Play purchase
      sheet, not this page, states the price and whether the product renews.
    """,
        ads_terms="""
      The free version contains advertising served by Google AdMob, with consent collected through
      Google's User Messaging Platform where required. An active Ad-Free or Kitchen Premium subscription
      removes advertising for the period you have paid for. Your pantry content is never passed to
      advertising.
    """,
        disclaimers=[
            "**Not food-safety or medical advice.** Pantry Pals records what you tell it. It does not inspect food, test freshness or decide whether something is safe to eat, and it cannot protect anyone with a food allergy or intolerance.",
            "**Always check the label.** Barcode and product data comes from the public OpenFoodFacts database, which is community-maintained, sometimes incomplete and sometimes wrong. For anaphylaxis risk, follow the allergen information printed on the packet and your own medical advice.",
            "**Nutrition and cost figures are estimates.** Nutrition values come from public data and the quantities you enter; cost figures come from what you type. Neither is a dietary, medical or financial assessment.",
            "**Use-by dates are yours, not ours.** Dates, reminders and expiry warnings depend on what you entered and on Android delivering notifications. Never treat a missing alert as proof that food is safe.",
            "**Shared means shared.** In a synced household, the other members can see and change the pantry, the profiles and the audit history. Do not store anything there you want kept private.",
            "**Keep a copy of anything you cannot afford to lose.** Sync can be paused, your account can be deleted and features can change; export your data if it matters.",
        ],
        not_stored="""
      We do not sell your data, and we do not use what is in your pantry &mdash; or which allergens a
      household profile records &mdash; for advertising or profiling. Without an account, nothing leaves
      your phone except the anonymous barcode lookups and the advertising and diagnostic traffic
      described above. We hold no readable copy of your pantry unless you deliberately switch on live
      sync.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>yes</strong> (email/password or Google, for the optional live-sync feature; the app is fully usable signed out and sync is off by default).",
            "Account creation is <strong>not required</strong> to use the app.",
            "Users can request deletion &mdash; <strong>yes</strong> (in-app More &rarr; Live sync &rarr; Delete account, by email, or by clearing app storage / uninstalling; this page is the deletion URL).",
            "Deletion requests are completed within <strong>90 days</strong>, and in-app account deletion is immediate.",
            "Data collected: pantry items, history, shopping list, household profiles and item photos are stored <strong>on the device</strong> and are collected by us only if you enable live sync; the optional account email is collected; app activity, diagnostics and device identifiers are collected by Firebase and Google AdMob.",
        ],


    ),
    app(
        slug="morse-beacon",
        name="Morse Beacon",
        package="com.luckytools.morse_beacon",
        theme="#64748b",
        footer_note="Morse practice and signalling tool — not an emergency, maritime or aviation device.",
        cloud=CLOUD_GATED_OFF,
        cloud_note=CLOUD_OFF_NOTE,
        services=[
            "The phone's torch (camera flash), used to flash Morse as light. The app does not request the camera permission and cannot capture a photo or a video",
            "Light haptic feedback, one short pulse per dot and dash; this uses Android's built-in haptics and needs no permission",
            "Notifications, for the practice reminders you switch on",
            "Network access, for advertising, purchases and optional diagnostics",
            "Your advertising ID, used by Google AdMob on the free tier",
        ],
        collected=[
            "**The messages you type, paste or decode.** Text is converted to Morse and back <strong>on your device</strong>. Nothing you type is transmitted to us, and the app has no message server.",
            "**Your learning progress.** Which character groups you have completed in the lesson path, the answers you gave, and your streak in the daily decode challenge, so the app can carry on where you left off.",
            "**Phrases you save.** Built-in presets are fixed; any custom phrase you write is stored on the device.",
            "**Recent messages**, if you are a Premium user and keep the on-device history.",
            "**Settings.** Speed, dot/dash timing, haptic, screen-flash and torch options, language and theme.",
            "**Diagnostics and analytics** described in the analytics section below.",
            "**Advertising data** processed by Google AdMob on the free tier.",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Lesson progress, completed character groups and your daily-challenge streak.",
            "Custom phrases and any recent messages you chose to keep.",
            "Timing, haptic, screen-flash, torch, language and theme settings.",
            "The locally cached Premium entitlement for this install.",
        ],
        ads="""
      The free tier shows advertising served by <strong>Google AdMob</strong>, with consent collected
      through <strong>Google's User Messaging Platform</strong> (UMP) where the law requires it. Google
      and its partners may process your advertising ID, IP address and device information to serve and
      measure ads. Advertising has no access to the messages you type, your saved phrases or your
      learning progress. An active Premium subscription or a lifetime purchase removes advertising.
    """,
        consent=True,
        analytics=FB_FULL,
        analytics_note="""
      We use Google Analytics for Firebase to understand which features are used, Crashlytics to
      receive crash and error reports, Performance Monitoring for startup and responsiveness, Remote
      Config to change feature switches without an app update, and Cloud Messaging to send push
      notifications if you allow them. Analytics events describe app behaviour (for example
      &ldquo;transmission started&rdquo;) and never contain the text you typed, your saved phrases or
      your message history. You can turn notifications off in Android settings at any time.
    """,
        monetisation="""
      Morse Beacon is free to download and supported by advertising. Two optional purchases are sold
      through Google Play Billing: a <strong>monthly auto-renewing subscription</strong> and a
      <strong>one-time lifetime unlock</strong>.
    """,
        products=[
            "<code>morse_beacon_premium</code> &mdash; monthly auto-renewing subscription (Google Play may also offer a free-trial base plan on it; the length of any trial and the price you pay afterwards are stated on Play's purchase sheet)",
            "<code>morse_beacon_lifetime</code> &mdash; one-time, non-consumable purchase that does not renew",
        ],
        plans_note="""
      Premium removes advertising and unlocks the full Koch-style lesson path beyond the first free
      character groups, the daily decode challenge, custom phrases and the on-device message history.
      The lifetime product is a single payment and never renews; the subscription renews every month
      until you cancel. Both grant the same features while they are active. <strong>Prices are never
      written on this page</strong>: Google Play is the merchant of record and shows the exact amount,
      including tax, on the sheet you confirm.
    """,
        ads_terms="""
      The free version contains banner and interstitial advertising served by Google AdMob, with
      advertising consent collected through Google's User Messaging Platform where the law requires it.
      Advertising never appears while your own transmission is in progress. An active Premium
      subscription or lifetime unlock removes advertising.
    """,
        disclaimers=[
            "**Not an emergency, rescue, maritime or aviation device.** Morse Beacon flashes a phone's torch or screen and pulses the phone's vibration motor. It is not a distress beacon, an EPIRB, a signal lamp, a radio or any kind of certified equipment, and nobody is listening on the other end. For any emergency, contact the emergency services on the proper channel.",
            "**A flash is only useful if someone is looking.** Light signalling needs line of sight and an attentive, competent receiver who knows Morse. Trees, weather, distance, daylight and the phone's own battery all defeat it &mdash; do not rely on this app to summon help or to keep anyone safe.",
            "**Do not flash at people or traffic.** Aiming a bright light at drivers, pilots, cyclists or anyone operating machinery is dangerous and can be unlawful, and flashing light can trigger photosensitivity reactions in some people. Point the torch away from eyes and never use the app while driving.",
            "**Heat and battery.** Running the torch continuously draws significant current and makes the phone hot. The LED can dim, thermal-throttle or switch off, and continuous use can damage the torch or drain the battery. Take breaks.",
            "**Morse is only as good as the operator.** Timing, spacing and character accuracy are yours. A mistyped character sends the wrong letter, and the app cannot know whether the other end copied you correctly.",
            "**Your transmission is public.** A flashing torch can be seen from a distance, and a phone buzzing on a table can be heard. Anyone nearby can read or hear what you send, so do not transmit anything you want kept private.",
        ],
        children="""
      Morse Beacon is a general-audience practice and signalling tool and is not directed at children.
      It is not part of Google Play's Families programme, advertising is not requested in
      child-directed mode, and there is no chat, no user-generated content shared between people and no
      way to contact another user through the app. We do not knowingly collect personal information
      from a child. If a child has used the app on a shared device, clearing the app's storage or
      uninstalling it removes everything held locally, and a parent or guardian can contact
      <a href="mailto:support@cloudyni.com">support@cloudyni.com</a>.
    """,
        retention="""
      Everything the app stores &mdash; lesson progress, streak, custom phrases, any kept messages and
      your settings &mdash; stays on your device until you clear it. You can wipe the stored history
      from inside the app (Settings &rarr; History &rarr; clear), and clearing the app's storage or
      uninstalling it removes the rest at once. Because there is no account and no server copy, we hold
      nothing of yours to expire. Support correspondence is kept only as long as needed to answer the
      query, and it is deleted on request, within 90 days. Firebase and AdMob data is retained by
      Google under our configuration and Google's own rules, and Google keeps purchase records as the
      merchant of record.
    """,
        not_stored="""
      We do not sell your data. The messages you send, the phrases you save and your learning progress
      stay on your phone: there is no account, no sync and no copy of them on our servers. In this
      release your data does not leave the device at all &mdash; the optional encrypted backup that
      would carry it is compiled in but switched off, so there is no control in the app that can upload
      anything.
    """,
        play_answers=CLOUD_OFF_ANSWERS + [
            "Data collected: the text you type, your phrases and your learning progress are <strong>not</strong> collected (on-device only); app activity, diagnostics and device identifiers may be collected by Firebase; advertising data and your advertising ID are collected by Google AdMob on the free tier; no account data is collected, because there is no account.",
            "Purchases: optional monthly subscription <code>morse_beacon_premium</code> and one-time <code>morse_beacon_lifetime</code>, sold through Google Play Billing.",
        ],
    ),
    # ── Spooky Sound Board ───────────────────────────────────────────────────
    # Profile: AdMob only (banner + interstitial, UMP consent), NO analytics of
    # any kind, and no Supabase/Firebase code in the build at all — CLOUD_NONE
    # here is literal, not a "dormant but switched off" claim like CLOUD_GATED_OFF.
    # One product, one payment: remove_ads_bonus. Haunted Doorway is the reason
    # the access list names a mediaPlayback foreground service, a partial wake
    # lock and notifications.
    app(
        slug="spooky-sound-board",
        name="Spooky Sound Board",
        package="com.cloudyni.spookysoundboard",
        theme="#ff7519",
        favicon="assets/icon-512.png",
        footer_note=(
            "Halloween sound effects — point the speakers at someone who asked for it."
        ),
        # First published after POLICY_DATE, so these pages carry their own date
        # rather than re-dating the other nine apps' policies.
        policy_date="30 September 2026",
        cloud=CLOUD_NONE,
        services=[
            "Your device's sound output, to play the 100 bundled sounds. The app never asks for the microphone and cannot record anything",
            "Haptic feedback, for the optional thump that fires with a Haunted Doorway scare; this uses Android's built-in vibration and needs no extra permission",
            "Notifications, asked for before a haunting can keep running with the screen off. Without that permission, scares only fire while the app is open",
            "A foreground service of type media playback, started only when you tap <em>Start the haunting</em>. It is what keeps scares firing while the screen is off, it shows a notification with <em>Stop</em> and <em>Scare now</em>, and it ends when you stop the haunting",
            "A partial wake lock, held only while a Haunted Doorway session is running, so the timer can fire on a sleeping screen",
            "Network access, for advertising on the free tier and for Google Play purchases",
            "Your advertising ID, used by Google AdMob on the free tier",
        ],
        collected=[
            "**Your favourites.** The sounds you starred, stored on the device and checked against the built-in catalogue every launch.",
            "**Your settings.** Master volume, vibration on tap, the thump a scare gives, keep-screen-awake, reduced motion, the scare flash, and whether a haunting keeps running with the screen off.",
            "**Your Haunted Doorway options.** The interval between scares, the auto-stop time, which sound groups the haunting draws on, screen flash and haptics.",
            "**A running haunting holds a countdown.** Whether a session is on, how many scares have fired and when the next one is due. This lives in memory while the session runs and is dropped the moment you stop it.",
            "**What you play is not kept.** Which sound you tapped is used to show what is playing on screen. It is not written to storage, and the app has no upload path at all.",
            "**Advertising data** processed by Google AdMob on the free tier (see the advertising section).",
            "**Correspondence** you send to support.",
        ],
        on_device=[
            "Your favourites, so the sounds you star are still starred after a restart.",
            "Volume, vibration, keep-awake, reduced-motion and scare-flash settings.",
            "Your Haunted Doorway options: interval, auto-stop time, sound groups, flash and haptics.",
            "The locally cached unlock for this install; the purchase itself belongs to your Google account.",
        ],
        ads="""
      The free tier shows a banner and occasional full-screen advertising served by
      <strong>Google AdMob</strong>. There is no mediator and no second ad network in this build:
      advertising, and the consent form that asks about it, both come straight from Google. Google
      may process your advertising ID, IP address and device information to serve and measure ads.
      AdMob never receives the sounds you play, your favourites, your settings or a running haunting.
      Once the one-time unlock is bought, the ad SDK is never initialised, so no ad is requested at
      all.
    """,
        consent=True,
        analytics=[],
        monetisation="""
      Spooky Sound Board is free to download and supported by advertising. A single
      <strong>one-time purchase</strong> through Google Play Billing removes advertising and unlocks
      the sixty-sound bonus pack. There is <strong>no subscription</strong> in this app, nothing
      renews, and no account is needed to buy it or to get it back.
    """,
        products=[
            "<code>remove_ads_bonus</code> &mdash; the one-time product the app requests from Google Play, which removes advertising and unlocks the bonus sound pack",
        ],
        one_off_only=True,
        plans_note="""
      The unlock is a <strong>one-off payment</strong>, not a subscription: there is no renewal, no
      recurring charge and nothing to cancel. A reinstall does not lose it either &mdash; the app
      asks Google Play on every launch, and <em>Restore a previous purchase</em> in Settings checks
      it again on demand. Buying it unlocks the Midnight Organ, the Zombie Horde, the Lurking Horror
      Theme, Child's Laughter, Call From Beyond and Blood Drip &amp; Splatter, and takes every ad out
      for good.
    """,
        ads_terms="""
      The free version contains a banner and occasional full-screen advertising served by Google
      AdMob. The one-time <code>remove_ads_bonus</code> purchase removes advertising permanently and
      unlocks the bonus sound pack. There is no subscription, so there is no recurring charge and
      nothing to cancel.
    """,
        disclaimers=[
            "**It is only as loud as your phone.** Loudness, audio quality and the delay between a tap and the sound depend on your device, its speaker and its case. There is no calibration, no amplifier and no volume beyond your phone's own maximum.",
            "**Pranks are your responsibility.** A sudden loud noise can frighten children, pets, and people with a heart condition, a hearing aid or sound sensitivity. Keep the volume reasonable, do not aim a scare at anyone who has not asked for one, and never use it where a startle could cause a fall or an accident.",
            "**The Haunted Doorway needs Android's cooperation.** Background scares depend on the notification permission, on your battery settings and on how your phone's manufacturer manages background work. Some devices stop it early, fire late, or suspend it when the phone is asleep or in battery saver.",
            "**A haunting is not meant to run for ever.** A session stops automatically after the time you choose (15 minutes up to 2 hours), when you tap <em>Stop the haunting</em>, when you stop it from its notification, or when the phone restarts.",
            "**Halloween entertainment, not equipment.** The app is a soundboard: it is not an alarm, a doorbell, a security device, a medical device or a safety device, and it must not be relied on for anything of that kind.",
            "**Sixty of the 100 sounds are in the bonus pack.** They play only after the one-time unlock, and until then they are left out of the Haunted Doorway rotation.",
        ],
        retention="""
      Everything the app stores &mdash; your favourites, your settings and your Haunted Doorway
      options &mdash; stays on your device until you reset them in the app, clear the app's storage
      or uninstall it. A running haunting keeps its countdown in memory only and drops it the moment
      you stop. Because there is no account and no server, we hold nothing of yours to expire or
      archive. Support correspondence is kept only as long as needed to answer the query, and it is
      deleted on request, within 90 days. AdMob data is retained by Google under our configuration
      and Google's own rules, and Google keeps purchase records as the merchant of record.
    """,
        not_stored="""
      We do not sell your data, and the app has no server of ours to send it to. Your favourites,
      your settings, the sounds you play and the state of a haunting stay on your phone: there is no
      account, no sign-in, no sync, no cloud backup and no copy of them anywhere else. The only third
      party the app talks to is Google, for advertising on the free tier and for the one-time Play
      purchase. There is no analytics SDK, no crash reporter and no advertising mediator in this
      build.
    """,
        play_answers=[
            "Users can create an account &mdash; <strong>no</strong>. The app has no sign-in, no account system and no server-side profile.",
            "Account creation is <strong>not required</strong> and is not available.",
            "Users can request deletion &mdash; <strong>yes</strong> (clearing app storage or uninstalling removes every favourite, setting and haunting preference at once; this page is the deletion URL).",
            "Deletion requests are completed within <strong>30 days</strong>.",
            "Data collected: favourites, settings and the sounds you play are stored on the device and are <strong>not</strong> collected by us; purchases are processed by Google Play Billing; device identifiers and advertising data may be processed by Google AdMob to serve ads on the free tier.",
        ],
    ),
    # APPS_MARKER
]


# ===========================================================================
# Writers
# ===========================================================================
# Everything below renders the APPS table above into the three legal pages for
# every canonical slug, plus a `noindex` redirect stub for every retired alias.
# Generated pages are never hand-edited: change the entry above and re-run.

POLICY_DATE = "27 September 2026"    # bump whenever an APPS entry changes
WIDTH = 98                           # wrap width used by every generated block


def policy_date(app):
    """The date this app's pages carry.

    A brand-new app can be added without re-dating every existing policy, so an
    entry may override the table date. Everything else keeps POLICY_DATE, which
    is bumped when the wording of an existing entry changes.
    """
    return app["policy_date"] or POLICY_DATE

ADMOB_PRIVACY = (
    '<a href="https://support.google.com/admob/answer/6128543" '
    'rel="noopener noreferrer" target="_blank">AdMob &amp; privacy</a>'
)
FIREBASE_PRIVACY = (
    '<a href="https://firebase.google.com/support/privacy" '
    'rel="noopener noreferrer" target="_blank">Firebase privacy and security</a>'
)
ICO_COMPLAINT = (
    '<a href="https://ico.org.uk/make-a-complaint/" rel="noopener noreferrer" '
    'target="_blank">raise a complaint with the ICO</a>'
)
CONSUMER_RIGHTS = (
    '<a href="https://www.legislation.gov.uk/ukpga/2015/15/contents" '
    'rel="noopener noreferrer" target="_blank">Consumer Rights Act 2015</a>'
)


def bold(text):
    """Turn the **emphasis** shorthand used throughout APPS into <strong>."""
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", str(text))


def para(text, indent="    "):
    """One reflowed, wrapped <p> block."""
    body = textwrap.fill(
        " ".join(str(text).split()),
        width=WIDTH,
        initial_indent=indent + "  ",
        subsequent_indent=indent + "  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return "%s<p>\n%s\n%s</p>\n" % (indent, body, indent)


def item_line(text, indent="      "):
    """One wrapped <li>; long list items stay inside the 98-column budget."""
    body = textwrap.fill(
        " ".join(bold(text).split()),
        width=WIDTH,
        initial_indent=indent + "<li>",
        subsequent_indent=indent + "  ",
        break_long_words=False,
        break_on_hyphens=False,
    )
    return body + "</li>\n"


def items_list(items, indent="      "):
    """A bulleted list built from plain strings or **emphasis** strings."""
    base = indent[:-2] or "  "
    out = "%s<ul>\n" % base
    for item in items:
        out += item_line(item, indent)
    return out + "%s</ul>\n" % base


def li_block(html, indent="      "):
    """Render a `<li>…</li>` fragment (the cloud_terms fields) as a clean <ul>."""
    found = re.findall(r"<li>(.*?)</li>", textwrap.dedent(str(html or "")), re.S)
    if not found:
        return frag(html, indent)
    return items_list(found, indent)


def frag(html, indent="    "):
    """Render one free-text APPS field as tidy prose blocks.

    Plain text becomes a <p> paragraph. A field that is already HTML keeps
    meaning: <br /> breaks become separate paragraphs, <li> runs become a <ul>,
    and any other tag run is treated as prose so its markup survives.
    """
    raw = textwrap.dedent(str(html or "")).strip()
    if not raw:
        return ""
    if not raw.startswith("<"):
        return para(bold(raw), indent)
    out = ""
    for chunk in re.split(r"<br\s*/?>", raw):
        chunk = chunk.strip()
        if not chunk:
            continue
        blocks = re.findall(r"<p>(.*?)</p>", chunk, re.S)
        if blocks:
            for inner in blocks:
                out += para(bold(inner), indent)
        elif chunk.startswith(("<ul", "<ol", "<li")):
            out += li_block(chunk, indent + "  ")
        else:
            out += para(bold(chunk), indent)
    return out


def note_block(html, indent="    "):
    """A `.note` callout wrapping generated prose (empty string if no prose)."""
    inner = frag(html, indent + "  ")
    if not inner:
        return ""
    return '%s<div class="note">\n%s%s</div>\n' % (indent, inner, indent)


def render(sections, intro=()):
    """Render (anchor, heading, blocks) triples with a matching table of contents.

    The intro blocks (the `.note` callout, usually) sit above the contents list,
    matching the layout of the pages this tool has always produced.
    """
    out = ""
    for extra in intro:
        out += extra
    out += toc([(a, h) for a, h, _ in sections])
    for anchor, heading, blocks in sections:
        out += h2(anchor, heading)
        out += "".join(b for b in blocks if b)
    return out


# ---------------------------------------------------------------------------
# Cloud posture. One table decides the wording, so no generated page can claim
# an account surface or a server copy that the released build does not have.
# ---------------------------------------------------------------------------
CLOUD_HEADING = {
    CLOUD_NONE: "Accounts and cloud services",
    CLOUD_GATED_OFF: "Accounts, backup and the switched-off cloud feature",
    CLOUD_OPTIN_E2E: "Optional encrypted cloud backup",
    CLOUD_LIVE_SYNC: "Optional live sync and sharing",
}

# The paragraph that closes the cloud section for each posture.
CLOUD_CLOSE = {
    CLOUD_NONE: (
        "There is no account system in this app, so there is nothing to sign in to and no"
        " server copy of your work exists for anyone to read, export or delete. If a cloud"
        " feature is ever added, the privacy policy and the"
        ' <a href="delete-data.html">data deletion</a> page will be updated before that'
        " build ships."
    ),
    CLOUD_GATED_OFF: (
        "Because that feature is switched off, this release creates no account and uploads"
        " nothing, so the"
        ' <a href="delete-data.html">data deletion</a> page has nothing on our side to'
        " delete. If we turn it on, we will update the privacy policy and publish the"
        " deletion route before that build ships."
    ),
    CLOUD_OPTIN_E2E: (
        "Deleting the account deletes the stored backup with it. Both routes &mdash; the"
        " in-app one and the email one &mdash; are set out on the"
        ' <a href="delete-data.html">data deletion</a> page.'
    ),
    CLOUD_LIVE_SYNC: (
        "Deleting the account removes the hosted copy and signs out every device that was"
        " sharing it. The"
        ' <a href="delete-data.html">data deletion</a> page explains what that erases and'
        " what stays on each device."
    ),
}


def cloud_section(app):
    """The account/cloud section, identical in shape on every page."""
    blocks = [frag(app["cloud_note"])]
    if app["cloud_terms"]:
        blocks.append(para("If you choose to use that optional feature, these rules apply:"))
        blocks.append(li_block(app["cloud_terms"]))
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC) and "Supabase" not in app["cloud_note"]:
        blocks.append(
            para(
                "The service that stores it is <strong>Supabase</strong>, acting as our"
                " processor on EU infrastructure: %s." % SUPABASE_PRIVACY
            )
        )
    blocks.append(para(CLOUD_CLOSE[app["cloud"]]))
    return ("cloud", CLOUD_HEADING[app["cloud"]], blocks)


def contact_section(app, anchor="contact", heading="Contact us", tail=""):
    """The closing section. `tail` adds one page-specific paragraph."""
    blocks = [
        para(
            "%s is a sole trader based in Northern Ireland, registered with the ICO for"
            ' data protection under reference <a href="%s" rel="noopener"'
            ' target="_blank">%s</a>.'
            % (CONTROLLER, ICO_URL, ICO)
        ),
        para(
            'Email <a href="mailto:%s">%s</a> for privacy questions, a purchase problem or'
            " a deletion request. We answer data-protection requests within one month and"
            " deletion requests within %d days."
            % (EMAIL, EMAIL, app["deletion_days"])
        ),
    ]
    if tail:
        blocks.append(para(tail))
    return (anchor, heading, blocks)


def privacy_sections(app):
    """(anchor, heading, blocks) for the privacy policy, in reading order."""
    sections = []

    sections.append((
        "who", "Who we are", [
            para(
                "This policy covers the <strong>%s</strong> Android app, package"
                ' <code>%s</code>, as published on Google Play by %s, together with the'
                " cloudyni.com pages that support it: this policy, the"
                ' <a href="terms.html">terms of use</a> and the'
                ' <a href="delete-data.html">data deletion</a> page.'
                % (app["name"], app["package"], CONTROLLER)
            ),
            para(
                "It describes the build that is on Google Play now. Where a feature is"
                " optional this policy says so, and where the app keeps nothing on our"
                " servers it says that too. We do not sell personal data."
            ),
        ],
    ))

    sections.append((
        "device", "What stays on your device", [
            para(
                "The following is written into the app's own private storage on your phone"
                " and is never sent to us:"
            ),
            items_list(app["on_device"]),
            para(
                "Clearing the app's storage or uninstalling the app deletes all of it at"
                " once, without contacting us. The"
                ' <a href="delete-data.html">data deletion</a> page lists the steps.'
            ),
        ],
    ))

    sections.append((
        "access", "What the app can access", [
            para(
                "The app asks Android for as little as it can. This is the complete list"
                " for the published build:"
            ),
            items_list(app["services"]),
            para(
                "An item above is used only while the feature that needs it is running, and"
                " nothing beyond this list is accessed by the app."
            ),
        ],
    ))

    sections.append((
        "handled", "Information the app handles", [
            para(
                "This is the full picture for the published build: everything the app"
                " records, processes or transmits, and where it goes."
            ),
            items_list(app["collected"]),
            *[frag(item) for item in app["privacy_extra"]],
        ],
    ))

    sections.append(cloud_section(app))

    if app["sensitive"]:
        sections.append((
            "sensitive", "Sensitive information", [
                frag(app["sensitive"]),
                para(
                    "Where that is special category data under UK GDPR &mdash; health"
                    " information, for example &mdash; the basis for using it is your explicit"
                    " consent, given when you choose to record it, and withdrawn by deleting the"
                    " entry. If the text above says the record stays on your device, your"
                    " device is the only place it is processed."
                ),
            ],
        ))

    if app["children"]:
        sections.append(("children", "Children and families", [frag(app["children"])]))

    if app["ads"]:
        ad_blocks = [frag(app["ads"])]
        if app["consent"]:
            ad_blocks.append(para(
                "Where the law requires it, the app asks for your advertising consent through"
                " <strong>Google's User Messaging Platform</strong> before it requests an"
                " advertisement, and you can change or withdraw that choice from the app's"
                " privacy options at any time."
            ))
        ad_blocks.append(para(
            "Advertising is served and measured by Google and its partners under %s and %s."
            " You can reset or delete your advertising ID, and turn personalised advertising"
            " off, in Android <em>Settings &rarr; Privacy &rarr; Ads</em>."
            % (GOOGLE_PRIVACY, ADMOB_PRIVACY)
        ))
        if app["products"]:
            ad_blocks.append(para(
                "Buying a paid product removes advertising for as long as that product is"
                " active; the next section explains what we learn from Google Play."
            ))
        sections.append(("ads", "Advertising", ad_blocks))

    analytics_blocks = []
    if app["analytics"]:
        analytics_blocks.append(para(
            "The app reports anonymous usage, performance and crash information through the"
            " Google services we configure:"
        ))
        analytics_blocks.append(items_list(app["analytics"]))
        analytics_blocks.append(para(
            "Those reports carry an app-instance identifier rather than your name, and Google"
            " handles them for us under %s. They are diagnostic: we use them to find crashes"
            " and to see which features are used, not to identify you." % FIREBASE_PRIVACY
        ))
    else:
        analytics_blocks.append(para(
            "This release contains no Google Analytics for Firebase, no Crashlytics and no"
            " third-party crash reporter, so nothing about how you use the app is reported"
            " anywhere."
        ))
    if app["analytics_note"]:
        analytics_blocks.append(frag(app["analytics_note"]))
    sections.append((
        "analytics", "Analytics, diagnostics and crash reports", analytics_blocks
    ))

    if app["extra_processors"]:
        rows = []
        for item in app["extra_processors"]:
            if isinstance(item, (tuple, list)):
                rows.append("**%s** %s" % (item[0], item[1]))
            else:
                rows.append(item)
        sections.append((
            "processors", "Other services that receive data", [
                para(
                    "Beyond Google Play and the services already named, these processors can"
                    " receive data from the app:"
                ),
                items_list(rows),
                para(
                    "Each is bound by its own privacy policy and by the terms we agree with it."
                    " A service acting only as our processor may use the data only to provide"
                    " that service to us."
                ),
            ],
        ))

    if app["products"]:
        sections.append((
            "purchases", "Purchases and subscriptions", [
                para(
                    "Anything you buy in %s is sold through <strong>Google Play Billing</strong>."
                    " Google is the merchant of record, so your payment method, billing address"
                    " and the amount you paid are held by Google and never shared with us."
                    % app["name"]
                ),
                para(
                    "To unlock a paid feature the app asks Google Play whether the product is"
                    ' active. The product identifiers are on the <a href="terms.html">terms of'
                    "</a> page, and the price is always the amount shown on the Google Play"
                    " purchase sheet when you confirm it. See %s and %s."
                    % (PLAY_TERMS, GOOGLE_PRIVACY)
                ),
                para(
                    "A subscription is cancelled in Google Play, not by deleting anything here,"
                    " and deleting your data does not cancel it."
                ) if not app["one_off_only"] else para(
                    "A one-time purchase never renews and needs no cancelling, and deleting your"
                    " data does not take it away: the app asks Google Play again the next time it"
                    " starts, so the unlock comes back at no extra cost."
                ),
            ],
        ))

    retention_blocks = []
    if app["retention"]:
        retention_blocks.append(frag(app["retention"]))
    else:
        retention_blocks.append(para(
            "Everything the app stores stays on your device until you clear its storage or"
            " uninstall it. Support email is kept only while the query is open and is deleted"
            " on request, within %d days." % app["support_days"]
        ))
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        retention_blocks.append(para(
            "A cloud copy is kept only for as long as the account exists; deleting the"
            " account, or asking us to delete it, erases it."
        ))
    else:
        retention_blocks.append(para(
            "Because this release keeps nothing on our servers, there is no record of yours"
            " for us to expire or archive."
        ))
    retention_blocks.append(para(
        "Google keeps purchase records and advertising data under its own policies, as the"
        " store and as an advertising provider rather than on our behalf."
    ))
    sections.append(("retention", "How long we keep things", retention_blocks))

    if app["cloud"] in (CLOUD_NONE, CLOUD_GATED_OFF):
        erasure = "Where we hold nothing about you, a request will confirm exactly that in writing."
    else:
        erasure = (
            "Where an account exists, deleting it erases the copy we hold: see the"
            ' <a href="delete-data.html">data deletion</a> page.'
        )
    sections.append((
        "rights", "Your rights", [
            para(
                "Under UK GDPR you can ask us for a copy of your information, ask us to correct"
                " or erase it, restrict or object to how we use it, ask for it in a portable"
                " format, and withdraw consent where consent is what we rely on."
            ),
            para(
                "Most of what this app holds is on your device, so you are the fastest route to"
                " erasure: delete the entries, clear the app's storage, or uninstall the app."
                " " + erasure
            ),
            para(
                'Email <a href="mailto:%s">%s</a> for any of these. We answer within one month'
                " and we do not charge for a first request. You can also %s if you are unhappy"
                " with how we have handled your information."
                % (EMAIL, EMAIL, ICO_COMPLAINT)
            ),
        ],
    ))

    security_blocks = [
        para(
            "Data kept by the app sits in its private app storage, inside Android's"
            " application sandbox, protected by your device lock and by Android's file-based"
            " encryption. Anything the app sends or receives travels over HTTPS."
        ),
    ]
    if app["security_extra"]:
        security_blocks.append(frag(app["security_extra"]))
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        security_blocks.append(para(
            "Cloud data is stored on EU infrastructure by our processor, transferred over"
            " TLS, and reachable only with the credentials that belong to the account."
        ))
    security_blocks.append(para(
        "No system is perfect. If we learn of a breach that puts your information at risk we"
        " will tell you and the ICO as UK GDPR requires; where we hold nothing about you,"
        " there is nothing for a breach to expose."
    ))
    sections.append(("security", "How we protect your data", security_blocks))

    sections.append((
        "changes", "Changes to this policy", [
            para(
                "This page was last updated on %s, and it describes the build that was on"
                " Google Play on that date. If a change affects what the app collects or where"
                " it goes, we update this page and the date above before the change ships. If"
                " the change is significant we will say so on the app's Google Play listing."
                % policy_date(app)
            ),
        ],
    ))

    sections.append(contact_section(
        app,
        tail=(
            "The exact steps for deleting data, and what to send us if you cannot use them,"
            ' are on the <a href="delete-data.html">data deletion</a> page.'
        ),
    ))
    return sections


def page_meta(app, date_label="Last updated"):
    """The doc-meta rows. Only the date label differs between the three pages."""
    return [
        ("App", "%s &middot; Android package <code>%s</code>" % (app["name"], app["package"])),
        ("Data controller", CONTROLLER),
        (
            "ICO data protection registration",
            '<a href="%s" rel="noopener" target="_blank">%s</a>' % (ICO_URL, ICO),
        ),
        ("Region", "Northern Ireland, United Kingdom"),
        (date_label, policy_date(app)),
        ("Contact", '<a href="mailto:%s">%s</a>' % (EMAIL, EMAIL)),
    ]


def build_privacy(app):
    """The full privacy.html for one app."""
    out = head(
        app,
        "privacy.html",
        "Privacy policy — %s" % app["name"],
        "How %s handles your information: what stays on your device, what is collected, and"
        " the choices you have." % app["name"],
    )
    out += header(app, "privacy")
    out += '\n  <main class="wrap doc">\n'
    out += "    <h1>Privacy policy</h1>\n"
    out += meta_block(page_meta(app))
    out += render(
        privacy_sections(app),
        intro=[note_block(app["not_stored"] or app["footer_note"])],
    )
    out += play_block(app)
    out += "\n  </main>\n"
    out += footer(app)
    return out


def terms_sections(app):
    """(anchor, heading, blocks) for the terms of use, in reading order."""
    sections = []

    sections.append((
        "agreement", "These terms", [
            para(
                "These terms are the agreement between you and %s, the publisher of"
                " <strong>%s</strong> (Android package <code>%s</code>). Installing or using"
                " the app means you accept them; if you do not accept them, do not use the app."
                % (CONTROLLER, app["name"], app["package"])
            ),
            para(
                "They cover the app and the cloudyni.com pages that support it, including the"
                ' <a href="privacy.html">privacy policy</a>. That policy explains what the app'
                " does with your information; these terms explain what you may and may not do"
                " with the app, and what we are responsible for."
            ),
        ],
    ))

    sections.append((
        "licence", "Your licence to use the app", [
            para(
                "We grant you a personal, non-exclusive, non-transferable, revocable licence to"
                " install and use the app on devices you own or control, for your own private"
                " use, for as long as these terms are in force."
            ),
            para("You must not:"),
            items_list([
                "copy, sell, rent, sublicense or redistribute the app, or make it available to anyone else;",
                "modify the app or create a derivative work from it;",
                "reverse engineer, decompile or try to extract source code, except to the extent that the law says the restriction cannot apply;",
                "remove or hide our notices, branding or attribution;",
                "use the app to break the law, to infringe anyone's rights, or in a way that breaks Google Play policy.",
            ]),
        ],
    ))

    sections.append((
        "store", "Google Play", [
            para(
                "The app is distributed through Google Play, so %s apply to you as well, and"
                " Google's own policies govern the store, the download and the payment."
                % PLAY_TERMS
            ),
            para(
                "Google is the merchant of record for anything you buy inside the app: it takes"
                " the payment, keeps the billing record, and handles refunds and billing"
                " disputes under its own policy. If your use of the app breaks Google Play's"
                " rules, Google can act against your Google account as well, which is outside"
                " our control."
            ),
        ],
    ))

    if app["monetisation"] or app["products"]:
        paid = [frag(app["monetisation"])]
        if app["plans_note"]:
            paid.append(frag(app["plans_note"]))
        if app["ads_terms"]:
            paid.append(frag(app["ads_terms"]))
        if app["products"]:
            paid.append(para("The product identifiers the app requests from Google Play are:"))
            paid.append(items_list(app["products"]))
            paid.append(frag(CATALOGUE_NOTE))
            paid.append(para("These rules apply to every purchase:"))
            paid.append(li_block(BILLING_RENEWAL))
        sections.append(("paid", "Free tier, advertising and paid products", paid))

    sections.append(cloud_section(app))

    use_blocks = [
        para(
            "You are responsible for how you use the app, for anything you enter, send or save"
            " in it, and for keeping your device and your account secure. Keep your own copy of"
            " anything you cannot afford to lose, and where the app can export or share your"
            " data, use it."
        ),
        para(
            "Do not try to interfere with the app, its servers or other users, do not try to"
            " unlock a paid feature without paying for it, and do not use the app in a way that"
            " breaks the law."
        ),
    ]
    if app["ads"]:
        use_blocks.append(para(
            "On the free tier, advertising is part of how the app is paid for. If you would"
            " rather not see it, buy the paid product or uninstall the app."
        ))
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        use_blocks.append(para(
            "If you create an account, keep your password to yourself. Anything done through"
            " your account is treated as done by you, so tell us straight away if you think"
            " somebody else has access to it."
        ))
    sections.append(("use", "Acceptable use and your responsibilities", use_blocks))

    sections.append((
        "content", "Content and ownership", [
            para(
                "The app itself, its design, its text, its icon and our branding belong to us or"
                " to our licensors, and nothing in these terms transfers any of that to you."
            ),
            para(
                "Anything you write, record, scan, photograph or save in the app stays yours. We"
                " claim no ownership over it, and where it never leaves your device we never even"
                " see it."
            ),
            para(
                "Where the app includes reference material supplied by someone else &mdash; a"
                " published text, a public dataset, a third-party image or a calculation method"
                " &mdash; that material stays the property of its supplier, and the limitations"
                " below explain what it can and cannot be used for."
            ),
        ],
    ))

    sections.append((
        "disclaimers", "Important limitations", [
            items_list(app["disclaimers"]),
            *[frag(item) for item in app["terms_extra"]],
            para(
                "These limitations are part of the app's design rather than small print added"
                " afterwards. If one of them rules out the way you need to use the app, then the"
                " app is not the right tool for that job, and you should not rely on it."
            ),
        ],
    ))

    sections.append((
        "liability", "Our liability", [
            para(
                "Nothing in these terms limits a right you have as a consumer that cannot be"
                " limited, and nothing here excludes our liability for death or personal injury"
                " caused by our negligence, for fraud, or for anything else the law does not"
                " allow us to exclude."
            ),
            para(
                "Subject to that, the app is provided as it is. We do not promise that it will"
                " be uninterrupted or error-free, or that it will suit a particular purpose, and"
                " we are not liable for indirect or consequential loss, for lost data, or for"
                " loss that was not reasonably foreseeable when you started using the app."
            ),
            para(
                "Subject to the first paragraph above, our total liability for any claim"
                " connected with the app is limited to the amount you paid for the app in the"
                " twelve months before the event that gave rise to the claim."
            ),
            para(
                "If you are a consumer in the UK, the %s gives you rights against us and against"
                " Google, and these terms do not reduce them." % CONSUMER_RIGHTS
            ),
        ],
    ))

    sections.append((
        "changes", "Changes to the app and to these terms", [
            para(
                "We may update the app and these terms. This is the current version, dated %s."
                " If we change the terms in a way that matters we will update this page before"
                " the change takes effect, and continuing to use the app after that means you"
                " accept the new version." % policy_date(app)
            ),
            para(
                "We may also change, suspend or withdraw the app, or a feature in it. If we"
                " withdraw something you have already paid for, we will deal with that in line"
                " with Google Play's policies and with your consumer rights."
            ),
        ],
    ))

    sections.append((
        "ending", "Ending this agreement", [
            para(
                "You can end this agreement at any time by uninstalling the app and, if you"
                ' created an account, deleting it as the <a href="delete-data.html">data'
                " deletion</a> page describes. Cancelling a subscription is separate and is done"
                " in Google Play."
            ),
            para(
                "We may end this agreement if you seriously break these terms. Where we do, we"
                " will tell you what happens to any account you hold, and the sections on your"
                " licence and on our liability continue to apply."
            ),
        ],
    ))

    sections.append((
        "law", "Governing law", [
            para(
                "These terms are governed by the law of Northern Ireland, and disputes may be"
                " brought in the courts of Northern Ireland. If you live elsewhere in the United"
                " Kingdom you can also bring a claim in your own courts, and nothing here stops"
                " you using a consumer advice service, a regulator or an alternative"
                " dispute-resolution scheme."
            ),
        ],
    ))

    sections.append(contact_section(
        app,
        tail=(
            "Questions about a charge, a receipt or a refund should go to Google Play first,"
            " because Google takes the payment; we can still help you work out what to ask for."
        ),
    ))
    return sections


def note_from_paras(*paras):
    """A `.note` callout built from plain strings, one <p> each."""
    inner = "".join(para(t, "      ") for t in paras if t)
    if not inner:
        return ""
    return '    <div class="note">\n%s    </div>\n' % inner


def terms_note(app):
    """The short summary at the top of terms.html: plain English, no repetition."""
    first = (
        "Short version: <strong>%s</strong> is licensed to you for your own private use, and"
        " anything you pay for is sold by Google Play, which is the merchant of record and"
        " handles refunds. The app is provided as it is, and the limitations in this page are"
        " meant to be read rather than skimmed." % app["name"]
    )
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        second = (
            "If you create an account, the rules for it are in the cloud section below, and the"
            " privacy policy says where that data is stored."
        )
    else:
        second = (
            "This release has no account to create, so none of your work is held on our"
            " servers."
        )
    return note_from_paras(first, second)


def build_terms(app):
    """The full terms.html for one app."""
    out = head(
        app,
        "terms.html",
        "Terms of use — %s" % app["name"],
        "The terms you accept when you use %s: your licence, purchases, limitations and our"
        " liability." % app["name"],
    )
    out += header(app, "terms")
    out += '\n  <main class="wrap doc">\n'
    out += "    <h1>Terms of use</h1>\n"
    out += meta_block(page_meta(app, "Effective date"))
    out += "\n"
    out += terms_note(app)
    out += "\n"
    out += render(terms_sections(app))
    out += play_block(app)
    out += "\n  </main>\n"
    out += footer(app)
    return out


# ---------------------------------------------------------------------------
# delete-data.html. This is the URL declared in Google Play Console's
# "data deletion" field, so it must work without JavaScript, without a login
# and without a support conversation: the device-side route is always first.
# ---------------------------------------------------------------------------
DELETE_HEADING = {
    CLOUD_NONE: "There is no account to delete",
    CLOUD_GATED_OFF: "There is no account to delete in this release",
    CLOUD_OPTIN_E2E: "Delete your account and its stored backup",
    CLOUD_LIVE_SYNC: "Delete your account and the shared copy",
}

DELETE_NOTE = {
    CLOUD_NONE: (
        "%s keeps everything on your device: no account, no server copy, nothing held by us."
        " Clearing the app's storage or uninstalling it is the complete deletion, and it takes"
        " effect immediately."
    ),
    CLOUD_GATED_OFF: (
        "%s has no sign-in in this release, so there is no account to delete and nothing of"
        " yours on our servers. The optional encrypted backup that exists in the app's code is"
        " switched off, so no copy can exist for us to delete."
    ),
    CLOUD_OPTIN_E2E: (
        "%s stores nothing on our servers unless you create an account and turn on the"
        " encrypted backup. Device data is deleted by clearing the app's storage; the account"
        " and its backup are deleted in the app or by email."
    ),
    CLOUD_LIVE_SYNC: (
        "%s keeps everything on your device unless you choose to share a list with another"
        " device. Device data is deleted by clearing the app's storage; the account and the"
        " hosted copy are deleted in the app or by email."
    ),
}

PAGE_LABELS = {
    "index.html": "home page",
    "privacy.html": "privacy policy",
    "terms.html": "terms of use",
    "delete-data.html": "data deletion page",
}


def plain_name(app):
    """The app name with HTML entities decoded, for <title> and mailto subjects."""
    return (
        app["name"]
        .replace("&amp;", "and")
        .replace("&mdash;", "-")
        .replace("&ndash;", "-")
    )


def delete_note(app):
    return DELETE_NOTE[app["cloud"]] % app["name"]


def local_steps(app):
    """The ordered device-side deletion route, the same on every page."""
    steps = []
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        steps.append(
            "If you created an account, delete it first, while you are still signed in, using"
            " the route in the next section."
        )
    steps.append(
        "Open Android <strong>Settings</strong> &rarr; <strong>Apps</strong> &rarr;"
        " <strong>%s</strong>." % app["name"]
    )
    steps.append(
        "Tap <strong>Storage</strong>, then <strong>Clear storage</strong>. That erases every"
        " entry, preference and cached file in one step."
    )
    steps.append(
        "To remove the app as well, tap <strong>Uninstall</strong> &mdash; or hold the app's"
        " icon on your home screen and choose <strong>Uninstall</strong>."
    )
    return ol(steps)


def account_blocks(app):
    """How an account or a stored backup is deleted, or why none exists."""
    if app["cloud_delete"]:
        blocks = [frag(app["cloud_delete"])]
        if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
            blocks.append(
                para(
                    "If you have already lost access to the account, use the email route"
                    " below: once we can confirm the account is yours, we will delete it and"
                    " everything attached to it."
                )
            )
        return blocks

    blocks = [
        para(
            "%s has no account system, so there is no profile, no sign-in and no server copy"
            " of your work for us to delete. Nothing you enter is stored on our servers, and"
            " the steps above are the whole of the deletion." % app["name"]
        )
    ]
    if app["cloud"] == CLOUD_GATED_OFF:
        blocks.append(
            para(
                "The app's code does contain a dormant, optional encrypted-backup feature, but"
                " it is switched off in the build you can download and there is no control that"
                " can enable it. No upload has happened, so no deletion is outstanding. If we"
                " ever ship that feature, this page will explain how to delete a backup before"
                " it does."
            )
        )
    return blocks


def email_blocks(app):
    """The email fallback Play requires, which must work even when nothing is stored."""
    subject = urllib.parse.quote("Data deletion request - %s" % plain_name(app))
    return [
        para(
            "If you cannot use the route above &mdash; or you left an account behind that you"
            ' can no longer reach &mdash; email <a href="mailto:%s?subject=%s">%s</a> and we'
            " will delete it for you." % (EMAIL, subject, EMAIL)
        ),
        para("Send the request from the address the account uses if you can, and include:"),
        items_list([
            "the email address you signed up with, so we can find the account;",
            "the Google Play order number from a purchase confirmation, if the request is about paid features;",
            "which of our apps the request is about, if you use more than one.",
        ]),
        para(
            "We will never ask for your password, your sign-in credentials, your ID documents"
            " or copies of what you saved in the app. Any message that does is not from us."
        ),
        para(
            "We check the request against the account, delete it, and reply to confirm."
            " Deletion requests are completed within <strong>%d days</strong>."
            % app["deletion_days"]
        ),
    ]


def deletion_rows(app):
    """What a deletion removes, and what legitimately stays behind."""
    rows = [
        "**On your device.** The entries, preferences and cached files the app saved. Clearing"
        " storage or uninstalling removes them at once, and no copy of them exists on our side.",
    ]
    if app["cloud"] in (CLOUD_OPTIN_E2E, CLOUD_LIVE_SYNC):
        rows.append(
            "**Your account and everything attached to it.** The email address you signed up"
            " with, the stored backup or shared data, and any device token that lets the app"
            " reach you."
        )
    rows.append(
        "**Support email.** The only thing we can hold about you if there is no account:"
        " deleted on request, and otherwise kept only while your query is open, for up to"
        " %d days." % app["support_days"]
    )
    rows.append(
        "**Purchase records.** Google keeps these, because it is the merchant of record, so"
        " they outlive a deletion request. We never see or hold your payment details."
    )
    if app["analytics"]:
        rows.append(
            "**Analytics and crash reports.** Reports already collected are not linked to your"
            " name; they are held on Google's retention schedule and expire on their own."
        )
    if app["ads"]:
        rows.append(
            "**Advertising data.** Held by Google and its mediated partners under their own"
            " policies, including your advertising ID, which you can reset or delete in Android"
            " settings at any time."
        )
    return rows


def billing_blocks(app):
    """The reminder that a Play purchase survives a deletion request."""
    if app["one_off_only"]:
        return [
            para(
                "Your unlock is a purchase record held by Google, not an account with us, so"
                " deleting your data does not remove it. Uninstalling and reinstalling the app does"
                " not remove it either: open the app on the same Google account and it asks Play"
                " whether the product is still active."
            ),
            para(
                "There is nothing to cancel, because the product is bought once and never renews."
                " Refunds and billing disputes are handled by Google as the merchant of record,"
                " under %s. If the unlock does not come back after a reinstall, email"
                ' <a href="mailto:%s">%s</a> with the Google Play order number from your purchase'
                " confirmation." % (PLAY_TERMS, EMAIL, EMAIL)
            ),
        ]
    return [
        para(
            "A purchase is a record held by Google, not an account with us, so deleting your"
            " data &mdash; or your account &mdash; does not cancel it. Uninstalling the app does"
            " not cancel it either."
        ),
        para(
            "To cancel, open Google Play &rarr; <em>Payments &amp; subscriptions</em> &rarr;"
            " <em>Subscriptions</em> and cancel the app there. Refunds are handled by Google as"
            " the merchant of record, under %s." % PLAY_TERMS
        ),
        para(
            "Cancelling stops the next charge; it does not end the period you have already paid"
            " for, so the paid features stay available until that period runs out."
        ),
    ]


def play_blocks(app):
    """The Play Data safety declaration, quoted so the page and the form agree."""
    return [
        para(
            "Google Play asks for a Data safety declaration for every app. These are the lines"
            " we declare for this build, and they match the sections above:"
        ),
        items_list(app["play_answers"]),
        para(
            "The declaration is reviewed whenever the app changes. If the app you have does not"
            ' match what is written here, tell us at <a href="mailto:%s">%s</a> and we will'
            " correct it." % (EMAIL, EMAIL)
        ),
    ]


def delete_sections(app):
    """(anchor, heading, blocks) for the deletion page, in reading order."""
    sections = [
        (
            "device",
            "Delete what is on your device",
            [
                para(
                    "You do not have to ask us for anything: everything the app saved on the"
                    " phone is removed by Android in a couple of taps, straight away."
                ),
                local_steps(app),
                para(
                    "Android's own device backup is separate from this app and belongs to your"
                    " Google account, so it is managed in <strong>Settings</strong> &rarr;"
                    " <strong>Google</strong> &rarr; <strong>Backup</strong>, not here."
                ),
            ],
        ),
        ("account", DELETE_HEADING[app["cloud"]], account_blocks(app)),
        ("email", "Ask us to delete it by email", email_blocks(app)),
        (
            "what",
            "What that deletes, and what stays",
            [
                items_list(deletion_rows(app)),
                para(
                    "Deletion is permanent. Once an account or its stored backup has gone, we"
                    " cannot restore it, so export anything you want to keep first."
                ),
            ],
        ),
    ]
    if app["products"]:
        sections.append((
            "billing",
            "Deleting data does not cancel your purchase"
            if app["one_off_only"]
            else "Deleting data does not cancel a subscription",
            billing_blocks(app),
        ))
    sections.append(("play", "What we declare to Google Play", play_blocks(app)))
    return sections


def build_delete_data(app):
    """The full delete-data.html for one app: the Play Console deletion URL."""
    out = head(
        app,
        "delete-data.html",
        "Delete your data — %s" % app["name"],
        "How to delete your %s data: what clearing the app's storage removes, and how to ask us"
        " to delete an account or a stored backup." % app["name"],
    )
    out += header(app, "delete-data")
    out += '\n  <main class="wrap doc">\n'
    out += "    <h1>Delete your data</h1>\n"
    out += meta_block(
        page_meta(app)
        + [("Deletion requests completed", "Within %d days" % app["deletion_days"])]
    )
    out += render(delete_sections(app), intro=[note_from_paras(delete_note(app))])
    out += play_block(app)
    out += "\n  </main>\n"
    out += footer(app)
    return out


# ---------------------------------------------------------------------------
# Retired alias slugs. These directories were once the canonical home of an app
# and their URLs are still registered in Google Play Console, so they must keep
# working. They get a self-contained `noindex,follow` redirect stub and are
# never given real legal pages again.
# ---------------------------------------------------------------------------
ALIASES = {
    "facts-kids": "factswipe",
    "bible-buddy": "religious-reader",
    "perimenopause-tracker-legal": "perimenopause-tracker",
}

STUB_PAGES = ("index.html", "privacy.html", "terms.html", "delete-data.html")


def check_table():
    """Fail loudly rather than silently overwriting the wrong app's pages."""
    seen = {}
    for a in APPS:
        if a["slug"] in seen:
            raise SystemExit("duplicate slug in APPS: %s" % a["slug"])
        for key in ("privacy_extra", "terms_extra", "play_answers"):
            if not isinstance(a[key], list):
                raise SystemExit("%s: %s must be a list" % (a["slug"], key))
        seen[a["slug"]] = a
    for alias, target in ALIASES.items():
        if target not in seen:
            raise SystemExit("alias %s points at unknown slug %s" % (alias, target))
    return seen


def stub_page(app, page):
    """One alias redirect stub, pointing at the same page on the canonical slug."""
    rel = (
        "../%s/" % app["slug"]
        if page == "index.html"
        else "../%s/%s" % (app["slug"], page)
    )
    url = "%s/%s/%s" % (SITE, app["slug"], "" if page == "index.html" else page)
    pretty = url.replace("https://", "")
    return (
        "<!DOCTYPE html>\n"
        '<html lang="en-GB">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        '  <meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        '  <meta http-equiv="refresh" content="0; url=%s" />\n'
        '  <meta name="robots" content="noindex,follow" />\n'
        '  <link rel="canonical" href="%s" />\n'
        "  <title>Moved &mdash; %s %s</title>\n"
        "</head>\n"
        "<body>\n"
        "  <p>\n"
        "    This page has moved. The %s for <strong>%s</strong> is now at\n"
        '    <a href="%s">%s</a>.\n'
        "  </p>\n"
        "  <p>\n"
        "    If your browser does not follow the redirect automatically, use the link above,\n"
        "    or open <a href=\"%s\">%s</a>.\n"
        "  </p>\n"
        "</body>\n"
        "</html>\n"
        % (
            rel,
            url,
            plain_name(app),
            PAGE_LABELS[page],
            PAGE_LABELS[page],
            app["name"],
            rel,
            pretty,
            url,
            pretty,
        )
    )


def write_page(path, text, check, changes):
    """Write `text` unless the file already matches; report what happened."""
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
    path.parent.mkdir(parents=True, exist_ok=True)
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
            if not target.exists():
                problems.append(
                    "%s -> %s" % (path.relative_to(ROOT).as_posix(), href)
                )
    return problems


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="tools_unify_app_pages.py",
        description=(
            "Regenerate privacy.html, terms.html and delete-data.html for every app in"
            " APPS, plus the redirect stubs for retired alias slugs."
        ),
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="dry run: report what would change, and exit 1 if anything would",
    )
    parser.add_argument(
        "--app",
        metavar="SLUG",
        help="restrict the run to one canonical slug (see --list)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="list the slugs, cloud posture and product counts, then exit",
    )
    parser.add_argument(
        "--urls",
        action="store_true",
        help="print the markdown URL table to paste into Play Console, then exit",
    )
    args = parser.parse_args(argv)

    table = check_table()

    if args.urls:
        print("| App | Privacy policy | Terms | Delete data | Website |")
        print("|-----|----------------|-------|-------------|---------|")
        for a in APPS:
            base = "%s/%s" % (SITE, a["slug"])
            print(
                "| %s | `%s/privacy.html` | `%s/terms.html` | `%s/delete-data.html` | `%s/` |"
                % (a["name"].replace("&amp;", "&"), base, base, base, base)
            )
        return 0

    if args.list:
        print("%-30s %-10s %8s  %s" % ("SLUG", "CLOUD", "PRODUCTS", "APP"))
        for a in APPS:
            print(
                "%-30s %-10s %8d  %s"
                % (a["slug"], a["cloud"], len(a["products"]), plain_name(a))
            )
        print("\naliases: " + ", ".join("%s -> %s" % kv for kv in sorted(ALIASES.items())))
        return 0

    if args.app and args.app not in table:
        print("unknown slug: %s (try --list)" % args.app, file=sys.stderr)
        return 2
    selected = [table[args.app]] if args.app else APPS
    wanted = {a["slug"] for a in selected}

    pages = []
    for a in selected:
        base = ROOT / a["slug"]
        if not base.is_dir():
            print("no such directory: %s" % base, file=sys.stderr)
            return 2
        pages.append((base / "privacy.html", build_privacy(a)))
        pages.append((base / "terms.html", build_terms(a)))
        pages.append((base / "delete-data.html", build_delete_data(a)))

    for alias in sorted(ALIASES):
        target = ALIASES[alias]
        if target not in wanted:
            continue
        base = ROOT / alias
        if not base.is_dir():
            print("%s: directory is gone, nothing to stub" % alias)
            continue
        for page in STUB_PAGES:
            # Stub every page the canonical app publishes, not only the ones this retired directory
            # happens to hold. `perimenopause-tracker-legal` was a legal-only folder, so it never had
            # an index.html or a delete-data.html - and both URLs answered 404 while this file's own
            # docs (`CLOUDYNI_URLS.md:8`, `PLAY_CONSOLE_URLS.md:24`) promised that every retired URL
            # still lands on the live page. The destination is what makes a stub safe: the canonical
            # page exists, so the redirect cannot point at nothing.
            if (base / page).exists() or (ROOT / target / page).exists():
                pages.append((base / page, stub_page(table[target], page)))

    changes = []
    for path, text in pages:
        write_page(path, text, args.check, changes)

    problems = internal_link_problems(pages)
    for problem in problems:
        print("BROKEN LINK  %s" % problem)

    if args.check:
        print(
            "\n--check: %d file(s) would change, %d broken link(s)"
            % (len(changes), len(problems))
        )
        return 1 if (changes or problems) else 0

    print("\n%d file(s) written, %d broken link(s)" % (len(changes), len(problems)))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

