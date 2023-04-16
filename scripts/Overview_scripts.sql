------Authors pr. country of citizenship
  SELECT 
    COUNT(*) cnt,
    country
  FROM authors a
  LEFT JOIN wikiauthors_reform a2 ON a2.author = a.author_q
  --WHERE (a.author_birth_year/100+1) = 15
  GROUP BY country
  ORDER BY cnt DESC;
------Authors pr. country of birth
  SELECT 
    COUNT(*) cnt,
    coalesce(author_birth_country,author_death_country) 
  FROM authors a
  GROUP BY coalesce(author_birth_country,author_death_country)
  ORDER BY cnt DESC;
--Texts by origin country
select count(*) cnt
	,a.country
from texts t
left join wikiauthors_reform a on a.author = t.text_author_q
group by a.country
order by cnt desc
select 
	t.text_title
	,t.text_q
	,t.text_author_q
	,a.author
	,a."authorLabel"
	,a.birthyear
	,a.country
from texts t
left join wikiauthors_reform a on a.author = t.text_author_q
where a.country is null
--Search Index
CREATE EXTENSION pg_trgm;
CREATE INDEX authors_search_idx ON authors USING GIN --Author index
(author_name gin_trgm_ops, author_nationality gin_trgm_ops
 , author_positions gin_trgm_ops, author_birth_city gin_trgm_ops
 , author_birth_country gin_trgm_ops, author_name_language gin_trgm_ops
 ,author_q gin_trgm_ops);
CREATE INDEX text_search_idx on texts USING GIN --Text index
(text_title gin_trgm_ops, text_author gin_trgm_ops
 , text_q gin_trgm_ops, text_author_q gin_trgm_ops);
---Search query
SELECT 
	author_id as value
	,CONCAT(
  SPLIT_PART(author_name, ', ', 1),
  COALESCE(
    CASE
      WHEN author_birth_year IS NULL AND author_death_year IS NULL AND author_floruit IS NULL THEN ''
      WHEN author_birth_year IS NULL AND author_death_year IS NULL THEN CONCAT(' (fl.', author_floruit, ')')
      WHEN author_birth_year IS NULL THEN CONCAT(' (d.', 
        COALESCE(
          CONCAT(ABS(author_death_year)::VARCHAR, ' BC'),
          author_death_year::VARCHAR
        ),
        ')')
      WHEN author_death_year IS NULL THEN CONCAT(' (b.', 
        COALESCE(
          CONCAT(ABS(author_birth_year)::VARCHAR, ' BC'),
          author_birth_year::VARCHAR
        ),
        ')')
      ELSE CONCAT(' (', ABS(author_birth_year), '-',
        COALESCE(
          CONCAT(ABS(author_death_year)::VARCHAR, ' BC'),
          author_death_year::VARCHAR
        ),
        ')')
    END,
    ''
  )
) AS label
FROM authors
WHERE author_name ILIKE '%@query%'
   OR author_nationality ILIKE '%@query%'
   OR author_positions ILIKE '%@query%'
   OR author_birth_city ILIKE '%@query%'
   OR author_birth_country ILIKE '%@query%'
   OR author_name_language ILIKE '%@query%'
   OR author_q ILIKE '%@query%'
ORDER BY ts_rank_cd(to_tsvector('simple', author_name || ' ' || author_nationality 
								|| ' ' || author_positions
								|| ' ' || author_birth_city
								|| ' ' || author_birth_country
								|| ' ' || author_name_language
								|| ' ' || author_q
							   ), plainto_tsquery('simple', 'query')) DESC;
select 
	text_id as value
	,text_title || 
	case
		when text_original_publication_year is null then ' - ' 
		when text_original_publication_year <0 then ' (' || abs(text_original_publication_year) || ' BC' || ') - '
		else ' (' || text_original_publication_year || ' AD' || ') - '
	end
	|| coalesce(text_author,'Unknown')
	as label
from texts
WHERE text_title ILIKE '%@query%'
	OR text_author ILIKE '%@query%'
	OR text_q ILIKE '%@query%'
	OR text_author_q ILIKE '%@query%'
ORDER BY ts_rank_cd(to_tsvector('simple', text_title || ' ' || text_author
							   || ' ' || text_q
								|| ' ' || text_author_q
							   ),plainto_tsquery('simple','query')) DESC;
   
