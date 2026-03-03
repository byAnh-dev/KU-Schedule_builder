import { useState, useEffect, useRef } from "react";
import { Search, Plus } from "lucide-react";
import { Input } from "./ui/input";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { searchCourses } from "../lib/data";
import { Course } from "../lib/types";
import { useScheduleStore } from "../store/useScheduleStore";

export function SearchPanel() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Course[]>([]);
  const [loading, setLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  
  const activeSemesterId = useScheduleStore((s) => s.activeSemesterId);
  const selectedCourses = useScheduleStore((s) => s.selectedCourses);
  const addCourse = useScheduleStore((s) => s.addCourse);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    const timer = setTimeout(async () => {
      if (query.trim().length > 1) {
        setLoading(true);
        const res = await searchCourses({ semesterId: activeSemesterId, query });
        setResults(res);
        setLoading(false);
        setIsOpen(true);
      } else {
        setResults([]);
        setIsOpen(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [query, activeSemesterId]);

  return (
    <div className="relative w-full" ref={ref}>
      <div className="relative">
        <Search className="absolute left-3 top-3 h-4 w-4 text-slate-400" />
        <Input
          placeholder="Search courses (e.g. EECS 388)"
          value={query}
          onChange={(e) => { setQuery(e.target.value); setIsOpen(true); }}
          onFocus={() => { if (query.trim().length > 1) setIsOpen(true); }}
          className="pl-9 w-full bg-white border-slate-300 shadow-sm"
        />
      </div>

      {isOpen && query.length > 1 && (
        <div className="absolute top-full left-0 right-0 mt-2 bg-portal-surface rounded-none shadow-none border border-portal-border z-50 max-h-[400px] overflow-y-auto p-2 flex flex-col gap-2">
          {loading && <p className="text-[14px] text-portal-text-secondary p-2">Searching...</p>}
          {!loading && results.length === 0 && (
            <p className="text-[14px] text-portal-text-secondary p-2">No courses found.</p>
          )}
          {results.map((course) => {
            const isAdded = selectedCourses.some((c) => c.id === course.id);

            return (
              <Card key={course.id} className="p-[12px] flex items-center justify-between hover:bg-slate-50 transition-colors border-portal-border">
                <div>
                  <h4 className="font-bold text-portal-text">{course.id}</h4>
                  <p className="text-[14px] text-portal-text-secondary">{course.title}</p>
                </div>
                <Button
                  size="sm"
                  variant={isAdded ? "portalSecondary" : "portalPrimary"}
                  disabled={isAdded}
                  onClick={() => {
                    addCourse(course);
                    setIsOpen(false);
                    setQuery("");
                  }}
                >
                  {isAdded ? "Added" : <><Plus className="h-4 w-4 mr-1" /> Add</>}
                </Button>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
