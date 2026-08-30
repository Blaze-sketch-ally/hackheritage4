import Link from "next/link";

export default function Page() {
  return (
    <div className="flex flex-col gap-4 p-8">
      <h1 className="text-xl font-semibold">Faculty Dashboard – Coming Soon</h1>
      <div className="flex gap-3 text-sm">
        <Link href="/faculty/questions" className="text-primary underline underline-offset-4">
          Question bank
        </Link>
        <Link href="/faculty/blueprint" className="text-primary underline underline-offset-4">
          Assessment blueprints
        </Link>
      </div>
    </div>
  );
}
