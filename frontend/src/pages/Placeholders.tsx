import { Link } from "react-router-dom";

export const Findings = () => <h1>Findings</h1>;
export const Methodology = () => <h1>Methodology</h1>;
export const About = () => <h1>About</h1>;

export function NotFound() {
  return (
    <>
      <h1>Not found</h1>
      <p>
        <Link to="/">Back to the ledger</Link>
      </p>
    </>
  );
}
