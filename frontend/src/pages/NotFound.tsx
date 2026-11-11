import { Compass } from "lucide-react";
import { Link } from "react-router-dom";
import { Button, EmptyState } from "@/components/ui";

export default function NotFound() {
  return <EmptyState icon={<Compass size={28} />} title="This page does not exist" text="The link may be old or mistyped." action={<Link to="/"><Button>Go home</Button></Link>} />;
}
