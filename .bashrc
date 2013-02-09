
[ `which fortune` ] && [ `which cowsay` ] && fortune | cowsay

# source bash_completion if not already
[ ! $BASH_COMPLETION_COMPAT_DIR ] &&
  if ! shopt -oq posix; then
    [ -f /usr/share/bash-completion/bash_completion ] && . /usr/share/bash-completion/bash_completion ||
    [ -f /etc/bash_completion ] && . /etc/bash_completion
  fi

PATH=$HOME/.local/bin:$PATH

# nicely colored prompt
PROMPT_DIRTRIM=4
PS1="\[\e[1;33;40m\]█▊▋▌▍▎▏\[\e[34m\][\[\e[31m\]\t\[\e[34m\]]\[\e[1;33m\]:\[\e[0;38;40m\]\w \[\e[1;33m\]\$\[\e[0m\] "
[ "$EUID" = "0" ] && PS1=${PS1//[1;33/[1;31}  # if root, make yellow red
PS1="${debian_chroot:+($debian_chroot)}${PS1}"
# ...with error reporting
PS1="\`RET=\$? ; [ \"\$RET\" != \"0\" ] && echo \"\[\e[31;40m\][Err:\${RET}]\[\e[0m\] \"\`${PS1}"

alias whois='whois -H'
alias more='less -R'
alias ls='ls --color=always -F'
alias la='ls -AlF'
alias ll='ls -lF'
alias grep='grep --color=always'
alias b64='base64'
alias b64d='base64 -d'

export PAGER=less
export LESS=-R
export EDITOR=geany
export VISUAL=geany
