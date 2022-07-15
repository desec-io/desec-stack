# https://stackoverflow.com/questions/59895/can-a-bash-script-tell-which-directory-it-is-stored-in
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

for file in $DIR/*.sql.var; do
	envsubst < $file > $DIR/`basename $file .var`
done
