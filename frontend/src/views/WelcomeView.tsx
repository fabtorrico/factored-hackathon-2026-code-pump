import { useNavigate } from "react-router-dom";

import { useSession } from "../state/SessionProvider";
import { ErrorNotice, Loading } from "../components/primitives";
import { humanize } from "../lib/format";

/**
 * The entry point.
 *
 * A visitor picks one of the demo profiles the backend derived from the curated data. The profile
 * is the only thing a caller chooses: the curated customer behind it is resolved in-process, so no
 * customer identifier is ever typed, guessed or sent from here.
 */
export function WelcomeView() {
  const { profiles, loadingProfiles, starting, error, chooseProfile, dismissError } = useSession();
  const navigate = useNavigate();

  async function start(profileId: string): Promise<void> {
    await chooseProfile(profileId);
    navigate("/", { replace: true });
  }

  return (
    <main className="page page--welcome">
      <header className="welcome__header">
        <p className="eyebrow">Code Pump</p>
        <h1 className="welcome__title">Banking support, decided by rules you can check.</h1>
        <p className="welcome__lede">
          Every answer on the next screens comes from a recorded movement in our systems. Nothing here
          guesses a cause, and nothing is marked resolved until our records actually say so.
        </p>
      </header>

      <section aria-labelledby="profiles-heading">
        <h2 id="profiles-heading" className="section-heading">
          Choose a demo customer
        </h2>
        <p className="muted">
          Each profile is a real curated customer whose history contains the situation it is here to
          demonstrate. Pick the one you want to see.
        </p>

        {error !== null && (
          <ErrorNotice title="The profiles could not be loaded" onDismiss={dismissError}>
            <p>{error}</p>
          </ErrorNotice>
        )}

        {loadingProfiles ? (
          <Loading label="Loading demo profiles" />
        ) : (
          <ul className="profiles">
            {profiles.map((profile) => (
              <li key={profile.profile_id}>
                <button
                  type="button"
                  className="profile"
                  onClick={() => void start(profile.profile_id)}
                  disabled={starting !== null}
                >
                  <span className="profile__name">{profile.display_name}</span>
                  <span className="profile__headline">{profile.headline}</span>
                  <span className="profile__facts">
                    <span className="chip">{profile.transaction_count} movements</span>
                    {profile.highlight_status !== null && (
                      <span className="chip">
                        {profile.highlight_count} {humanize(profile.highlight_status)}
                      </span>
                    )}
                  </span>
                  <span className="profile__go">
                    {starting === profile.profile_id ? "Opening…" : "Continue"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <footer className="welcome__footer">
        <p className="muted">
          This is a prototype reading a de-identified copy of a banking dataset. No real account is
          involved and no personal data is shown.
        </p>
      </footer>
    </main>
  );
}